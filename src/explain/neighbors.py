"""'Nasabah yang mirip' (PRD pillar explainability, graph): for each NBO recommendation, the
share of the customer's 50 nearest neighbours in the month-(t-1) graph embedding that
already hold the product. Uses only month t-1 holdings, never the label month."""
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from src.config import path


def build(k: int = 50, top: int = 3) -> pd.DataFrame:
    s = pd.read_parquet(path("processed") / "scores" / "nbo_test.parquet")
    t = int(s["bulan_label"].max())
    s = s.sort_values(["person_id", "skor"], ascending=[True, False])
    rec = s.groupby("person_id").head(top)
    gr = pd.read_parquet(path("processed") / "graph" / f"graph_w{t - 1}.parquet").set_index("id")
    panel = pd.read_parquet(path("processed") / "clean" / "nasabah_bulanan.parquet")
    prev = panel[panel["bulan_ke"] == t - 1].set_index("person_id")
    people = prev.index.intersection(gr.index)
    E = gr.loc[people, [c for c in gr.columns if c.startswith("emb_")]].to_numpy()
    nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine", algorithm="brute").fit(E)
    who = rec["person_id"].unique()
    pos = pd.Series(np.arange(len(people)), index=people)
    q = pos.reindex(who).dropna().astype(int)
    _, idx = nn.kneighbors(E[q.to_numpy()])
    neigh = pd.DataFrame({"person_id": q.index, "tetangga": list(idx[:, 1:])}).set_index("person_id")["tetangga"]
    held = {c: prev[c].reindex(people).to_numpy() for c in rec["kolom"].unique()}
    rec = rec[rec["person_id"].isin(neigh.index)].copy()
    rec["porsi_tetangga_memegang"] = [held[c][neigh[p]].mean() for p, c in zip(rec["person_id"], rec["kolom"])]
    # A raw share is hard to read for rare products (2% can be a strong signal), so compare it
    # with the share among all customers: lift 3x = similar customers hold it 3 times as often.
    overall = {c: float(np.nanmean(v)) for c, v in held.items()}
    rec["porsi_semua_nasabah"] = rec["kolom"].map(overall)
    rec["lift_tetangga"] = rec["porsi_tetangga_memegang"] / rec["porsi_semua_nasabah"].where(rec["porsi_semua_nasabah"] > 0)
    rec["jumlah_tetangga"] = k
    out = rec[["person_id", "produk", "kolom", "skor", "porsi_tetangga_memegang", "porsi_semua_nasabah", "lift_tetangga",
               "jumlah_tetangga"]]
    out.to_parquet(path("processed") / "explain" / "nbo_tetangga.parquet", index=False)
    return out
