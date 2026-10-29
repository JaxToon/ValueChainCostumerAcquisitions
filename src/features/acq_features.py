"""Features for the acquisition engine, one row per prospect per walk-forward window.

Only what the bank can see by the window's feature month `last`: visible transfers up to
`last`, who was a Bank customer by then (static customers + prospects that joined in an
earlier window), public company data (sector), and graph outputs for that month.
Window k candidates = prospects not yet joined; label = joins in window k's label months.
"""
import numpy as np
import pandas as pd
from scipy import sparse

from src.config import path, settings

TABLE = ["tipe_perusahaan", "peran_pedagang", "peran_karyawan", "sektor", "log_nominal_total",
         "log_jumlah_transaksi", "bulan_aktif", "n_tetangga", "tren_nominal_3bln"]
GRAPH = ["log_nominal_dengan_bank", "porsi_tetangga_bank", "bulan_aktif_dengan_bank", "porsi_bank_dua_langkah",
         "tetangga_baru_bergabung", "pagerank", "porsi_bank_komunitas", "mirip_nasabah_bank"]
# Raw FastRP coordinates are not aligned across windows (each window's graph is embedded
# separately), so models use only rotation-free similarities computed inside one window.


def clean(name: str) -> pd.DataFrame:
    return pd.read_parquet(path("processed") / "clean" / f"{name}.parquet")


def build_window(k: int, last: int, end: int, emb_dim: int = 64) -> pd.DataFrame:
    tr, acq = clean("transfers"), clean("acquisitions")
    persons, comp, emp = clean("persons"), clean("companies"), clean("employment")
    joined = acq[(acq["jendela"] > 0) & (acq["jendela"] < k)]["entity_id"]
    own_cust = set(persons.loc[persons["is_bank_customer"] == 1, "person_id"]) | set(comp.loc[comp["is_bank_customer"] == 1, "company_id"]) | set(joined)

    lookback = settings()["windows"]["lookback_bulan"]
    w = tr[(tr["bulan_ke"] <= last) & (tr["bulan_ke"] > last - lookback)]
    e = pd.concat([w.rename(columns={"from_id": "src", "to_id": "dst"}), w.rename(columns={"to_id": "src", "from_id": "dst"})])
    e["dst_bank"] = e["dst"].isin(own_cust)
    g = e.groupby("src")
    f = pd.DataFrame({
        "log_nominal_total": np.log1p(g["total_nominal_rp"].sum()),
        "log_jumlah_transaksi": np.log1p(g["jumlah_transaksi"].sum()),
        "bulan_aktif": g["bulan_ke"].nunique(),
        "n_tetangga": g["dst"].nunique(),
    })
    eb = e[e["dst_bank"]].groupby("src")
    f["log_nominal_dengan_bank"] = np.log1p(eb["total_nominal_rp"].sum()).reindex(f.index).fillna(0)
    f["bulan_aktif_dengan_bank"] = eb["bulan_ke"].nunique().reindex(f.index).fillna(0)
    pairs = e.drop_duplicates(["src", "dst"])
    f["porsi_tetangga_bank"] = pairs.groupby("src")["dst_bank"].mean().reindex(f.index).fillna(0)
    recent = e[e["bulan_ke"] > last - 3].groupby("src")["total_nominal_rp"].sum()
    before = e[(e["bulan_ke"] <= last - 3) & (e["bulan_ke"] > last - 6)].groupby("src")["total_nominal_rp"].sum()
    f["tren_nominal_3bln"] = np.log1p(recent.reindex(f.index).fillna(0)) - np.log1p(before.reindex(f.index).fillna(0))

    # Share of Bank accounts two steps away (colleagues, the anchor's other partners).
    ids = pd.Index(sorted(set(pairs["src"]) | set(pairs["dst"])))
    i, j = ids.get_indexer(pairs["src"]), ids.get_indexer(pairs["dst"])
    adj = sparse.csr_matrix((np.ones(len(i)), (i, j)), shape=(len(ids), len(ids)))
    is_bank = ids.isin(own_cust).astype(float)
    deg = np.asarray(adj.sum(axis=1)).ravel()
    paths, bank_paths = adj @ deg - deg, adj @ (adj @ is_bank) - deg * is_bank
    two = pd.Series(np.where(paths > 0, bank_paths / np.maximum(paths, 1), 0.0), index=ids)
    f["porsi_bank_dua_langkah"] = two.reindex(f.index).fillna(0)

    # Contagion the bank can see: neighbours that became customers in the last 3 months.
    recent_join = set(acq.loc[(acq["jendela"] > 0) & (acq["jendela"] < k) & (acq["bulan_jadi_nasabah"] > last - 3), "entity_id"])
    f["tetangga_baru_bergabung"] = pairs[pairs["dst"].isin(recent_join)].groupby("src").size().reindex(f.index).fillna(0)

    gr = pd.read_parquet(path("processed") / "graph" / f"graph_w{last}.parquet").set_index("id")
    com_share = gr.assign(b=gr.index.isin(own_cust)).groupby("komunitas")["b"].mean()
    f["pagerank"] = gr["pagerank"].reindex(f.index)
    f["porsi_bank_komunitas"] = gr["komunitas"].map(com_share).reindex(f.index)
    emb_cols = [f"emb_{d}" for d in range(emb_dim)]
    E = gr[emb_cols]
    U = E.div(np.linalg.norm(E.to_numpy(), axis=1) + 1e-9, axis=0)
    is_comp = U.index.str.startswith("C")
    sims = pd.Series(np.nan, index=U.index)
    for mask in [is_comp, ~is_comp]:
        ref = U[mask & U.index.isin(own_cust)].mean().to_numpy()
        sims[mask] = U[mask].to_numpy() @ (ref / (np.linalg.norm(ref) + 1e-9))
    f["mirip_nasabah_bank"] = sims.reindex(f.index)
    joiners = U.index.intersection(pd.Index(joined))
    if len(joiners):
        ref = U.loc[joiners].mean().to_numpy()
        f["mirip_yang_baru_bergabung"] = pd.Series(U.to_numpy() @ (ref / (np.linalg.norm(ref) + 1e-9)), index=U.index).reindex(f.index)
    else:
        f["mirip_yang_baru_bergabung"] = np.nan
    f = f.join(gr[emb_cols], how="left")

    # Candidates of this window and their label.
    cand = acq[(acq["jendela"] == 0) | (acq["jendela"] >= k)].copy()
    cand["label"] = (cand["jendela"] == k).astype(int)
    roles = emp.drop_duplicates("person_id").set_index("person_id")["peran"]
    employer = emp.drop_duplicates("person_id").set_index("person_id")["company_id"]
    sector = comp.set_index("company_id")["sektor"]
    cand["tipe_perusahaan"] = (cand["tipe"] == "PERUSAHAAN").astype(int)
    cand["peran_pedagang"] = cand["entity_id"].map(roles).eq("PEMBELI").astype(int)
    cand["peran_karyawan"] = cand["entity_id"].map(roles).eq("KARYAWAN").astype(int)
    cand["sektor"] = np.where(cand["tipe"] == "PERUSAHAAN", cand["entity_id"].map(sector),
                              cand["entity_id"].map(employer).map(sector))
    cand["sektor"] = cand["sektor"].fillna("NA").astype("category")
    out = cand.set_index("entity_id").join(f, how="left")
    out[TABLE[4:] + GRAPH[:5]] = out[TABLE[4:] + GRAPH[:5]].fillna(0)
    out["jendela_k"], out["bulan_fitur_terakhir"] = k, last
    return out.reset_index()


def build_all() -> pd.DataFrame:
    w = settings()["windows"]["akuisisi"]
    df = pd.concat([build_window(k, a, b) for k, (a, b) in enumerate(w, start=1)], ignore_index=True)
    dst = path("processed") / "features"
    dst.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dst / "akuisisi.parquet", index=False)
    return df
