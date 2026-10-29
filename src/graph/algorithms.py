"""Graph algorithms per walk-forward window, run in Neo4j GDS and exported to files.

For a feature month `last`, the projection holds only what was known by then: transfers
up to `last` (weight = log10 of total nominal), product holdings/uses active in `last`,
and person-company links. Undirected, so FastRP and Louvain see both directions.
Output: data/processed/graph/graph_w{last}.parquet with id, pagerank, komunitas, emb_*.
"""
import numpy as np
import pandas as pd

from src.config import path, settings
from src.graph.ingest import connect

PROJECT = """
CALL {
  MATCH (s:Entity)-[r:TRANSFER]->(t:Entity) WHERE r.bulan_ke <= $last
  WITH s, t, sum(r.nominal) AS total
  RETURN s, t, log10(1 + total) AS w
  UNION ALL
  MATCH (s:Person)-[h:HOLDS]->(t:Product) WHERE h.mulai <= $last AND h.selesai >= $last
  RETURN s, t, 1.0 AS w
  UNION ALL
  MATCH (s:Company)-[u:USES]->(t:Product) WHERE u.mulai <= $last AND u.selesai >= $last
  RETURN s, t, 1.0 AS w
  UNION ALL
  MATCH (s:Person)-[:WORKS_AT|OWNS|BUYS_FROM]->(t:Company)
  RETURN s, t, 1.0 AS w
}
WITH gds.graph.project($name, s, t, {relationshipProperties: {w: w}}, {undirectedRelationshipTypes: ['*']}) AS g
RETURN g.graphName AS name, g.nodeCount AS nodes, g.relationshipCount AS rels
"""


def windows() -> list[int]:
    w = settings()["windows"]
    months = {a for a, _ in w["akuisisi"]} | {a for a, _ in w["wholesale"]} | {m - 1 for m in w["nbo_label_bulan"]}
    return sorted(months)


def run_window(gds, last: int) -> pd.DataFrame:
    cfg = settings()["graph"]
    name = f"w{last}"
    if gds.graph.exists(name)["exists"]:
        gds.graph.drop(name)
    info = gds.run_cypher(PROJECT, {"last": last, "name": name}).iloc[0]
    G = gds.graph.get(name)
    emb = gds.fastRP.stream(G, embeddingDimension=cfg["fastrp_dim"], relationshipWeightProperty="w",
                            iterationWeights=cfg["fastrp_iterations"], randomSeed=cfg["random_seed"])
    pr = gds.pageRank.stream(G, relationshipWeightProperty="w")
    lv = gds.louvain.stream(G, relationshipWeightProperty="w")
    G.drop()
    ids = gds.run_cypher("MATCH (n) WHERE n:Entity OR n:Product RETURN id(n) AS nodeId, n.id AS id")
    E = pd.DataFrame(np.vstack(emb["embedding"].to_numpy()), columns=[f"emb_{i}" for i in range(cfg["fastrp_dim"])])
    E["nodeId"] = emb["nodeId"].to_numpy()
    out = (ids.merge(E, on="nodeId")
              .merge(pr.rename(columns={"score": "pagerank"}), on="nodeId", how="left")
              .merge(lv.rename(columns={"communityId": "komunitas"}), on="nodeId", how="left")
              .drop(columns="nodeId"))
    out.attrs.update({"nodes": int(info["nodes"]), "rels": int(info["rels"])})
    return out


def run_all() -> dict:
    gds = connect()
    dst = path("processed") / "graph"
    dst.mkdir(parents=True, exist_ok=True)
    summary = {}
    for last in windows():
        df = run_window(gds, last)
        df.to_parquet(dst / f"graph_w{last}.parquet", index=False)
        summary[last] = {"node": df.attrs["nodes"], "relasi": df.attrs["rels"], "komunitas": int(df["komunitas"].nunique())}
        print(f"jendela fitur bulan {last}: {summary[last]}", flush=True)
    return summary


if __name__ == "__main__":
    run_all()
