"""Load the cleaned bank view into Neo4j as one knowledge graph.

Nodes:  Person, Company (both also :Entity, the parties of a transfer), Product, RM.
Edges:  TRANSFER {bulan_ke, nominal, n, jenis}    monthly money flow between entities
        HOLDS    {mulai, selesai}                 a person's product holding spell (bulan_ke)
        USES     {mulai, selesai}                 a company's product use (bulan_ke; <1 = before panel)
        WORKS_AT / OWNS / BUYS_FROM               person -> company (employment.csv)
        MANAGED_BY                                company -> RM
Every edge carries months, so a window's graph can be cut at its feature month (no lookahead).
"""
import numpy as np
import pandas as pd
from graphdatascience import GraphDataScience

from src.config import env, path, settings

ROLE_EDGE = {"KARYAWAN": "WORKS_AT", "PEMILIK": "OWNS", "PEMBELI": "BUYS_FROM"}


def connect() -> GraphDataScience:
    e = env()
    return GraphDataScience(e["NEO4J_URI"], auth=(e["NEO4J_USER"], e["NEO4J_PASSWORD"]),
                            database=settings()["neo4j"]["database"])


def clean(name: str) -> pd.DataFrame:
    return pd.read_parquet(path("processed") / "clean" / f"{name}.parquet")


def month_index(dates: pd.Series) -> pd.Series:
    """bulan_ke of a date: 2025-01 = 1; dates before the panel give <= 0; empty -> 999."""
    d = pd.to_datetime(dates, errors="coerce")
    return ((d.dt.year - 2025) * 12 + d.dt.month).fillna(999).astype(int)


def holding_spells(panel: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    """Contiguous months a person holds a product -> one row (person, product, mulai, selesai)."""
    out = []
    p = panel.sort_values(["person_id", "bulan_ke"])
    for col, product in columns.items():
        x = p[["person_id", "bulan_ke", col]]
        x = x[x[col] == 1]
        if x.empty:
            continue
        new = (x["person_id"] != x["person_id"].shift()) | (x["bulan_ke"] != x["bulan_ke"].shift() + 1)
        x = x.assign(run=new.cumsum())
        s = x.groupby("run").agg(person_id=("person_id", "first"), mulai=("bulan_ke", "min"), selesai=("bulan_ke", "max"))
        out.append(s.assign(product=product))
    return pd.concat(out, ignore_index=True)


def batches(gds, query: str, rows: pd.DataFrame, size: int):
    records = rows.replace({np.nan: None}).to_dict("records")
    for i in range(0, len(records), size):
        gds.run_cypher(query, {"rows": records[i:i + size]})


def ingest(reset: bool = True) -> dict:
    gds, size = connect(), settings()["neo4j"]["batch"]
    if reset:
        gds.run_cypher("CALL apoc.periodic.iterate('MATCH (n) RETURN n', 'DETACH DELETE n', {batchSize: 20000})")
    for label in ["Person", "Company", "Product", "RM"]:
        gds.run_cypher(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")
    gds.run_cypher("CREATE INDEX entity_id IF NOT EXISTS FOR (n:Entity) ON (n.id)")
    gds.run_cypher("CALL db.awaitIndexes(300)")

    persons, nasabah = clean("persons"), clean("nasabah")
    persons = persons.merge(nasabah[["person_id", "kisaran_pendapatan", "channel"]], on="person_id", how="left", suffixes=("", "_n"))
    batches(gds, """UNWIND $rows AS r MERGE (p:Person:Entity {id: r.person_id})
                    SET p.is_bank = r.is_bank_customer, p.usia = r.usia, p.pekerjaan = r.pekerjaan,
                        p.provinsi = r.provinsi, p.bank_utama = r.bank_utama""", persons, size)

    comp = clean("companies")
    batches(gds, """UNWIND $rows AS r MERGE (c:Company:Entity {id: r.company_id})
                    SET c.is_bank = r.is_bank_customer, c.is_anchor = r.is_anchor, c.sektor = r.sektor,
                        c.provinsi = r.provinsi, c.segmen = r.segmen_bank, c.bank_utama = r.bank_utama,
                        c.nama = r.nama_samaran""", comp, size)

    levels = clean("produk_level")
    panel = clean("nasabah_bulanan")
    retail = {c: c for c in panel.columns if c.startswith("prod_")}
    names = dict(zip(levels["kolom"], levels["produk"]))
    retail = {c: names.get(c, c.removeprefix("prod_").replace("_", " ").title()) for c in retail}
    hist, fac = clean("riwayat_produk_wholesale"), clean("fasilitas_pembiayaan")
    products = pd.DataFrame({"id": sorted(set(retail.values()) | set(hist["produk"]) | set(fac["produk"]))})
    products["segmen_produk"] = np.where(products["id"].isin(retail.values()), "ritel", "bisnis")
    batches(gds, "UNWIND $rows AS r MERGE (p:Product {id: r.id}) SET p.segmen = r.segmen_produk", products, size)

    spells = holding_spells(panel, retail)
    batches(gds, """UNWIND $rows AS r MATCH (p:Person {id: r.person_id}), (q:Product {id: r.product})
                    CREATE (p)-[:HOLDS {mulai: r.mulai, selesai: r.selesai}]->(q)""", spells, size)

    uses = pd.concat([
        hist.assign(mulai=month_index(hist["tanggal_mulai"]), selesai=month_index(hist["tanggal_selesai"].replace("", None)))[
            ["company_id", "produk", "mulai", "selesai"]],
        fac.assign(mulai=month_index(fac["tanggal_mulai"]), selesai=month_index(fac["jatuh_tempo"]))[
            ["company_id", "produk", "mulai", "selesai"]]], ignore_index=True)
    batches(gds, """UNWIND $rows AS r MATCH (c:Company {id: r.company_id}), (q:Product {id: r.produk})
                    CREATE (c)-[:USES {mulai: r.mulai, selesai: r.selesai}]->(q)""", uses, size)

    emp = clean("employment")
    for role, rel in ROLE_EDGE.items():
        rows = emp[emp["peran"] == role][["person_id", "company_id"]]
        batches(gds, f"""UNWIND $rows AS r MATCH (p:Person {{id: r.person_id}}), (c:Company {{id: r.company_id}})
                         MERGE (p)-[:{rel}]->(c)""", rows, size)

    rm = clean("rm_portofolio")
    batches(gds, """UNWIND $rows AS r MERGE (m:RM {id: r.rm_id}) SET m.cabang = r.cabang
                    WITH m, r MATCH (c:Company {id: r.company_id}) MERGE (c)-[:MANAGED_BY]->(m)""", rm, size)

    tr = clean("transfers").rename(columns={"total_nominal_rp": "nominal", "jumlah_transaksi": "n", "jenis_relasi_terlihat": "jenis"})
    batches(gds, """UNWIND $rows AS r MATCH (a:Entity {id: r.from_id}), (b:Entity {id: r.to_id})
                    CREATE (a)-[:TRANSFER {bulan_ke: r.bulan_ke, nominal: r.nominal, n: r.n, jenis: r.jenis}]->(b)""",
            tr[["from_id", "to_id", "bulan_ke", "nominal", "n", "jenis"]], size)

    counts = gds.run_cypher("""CALL { MATCH (n) RETURN count(n) AS nodes }
                               CALL { MATCH ()-[r]->() RETURN count(r) AS edges } RETURN nodes, edges""")
    return counts.iloc[0].to_dict()


if __name__ == "__main__":
    print(ingest())
