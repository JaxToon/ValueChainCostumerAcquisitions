"""Features for the NBO engine: one row per (customer, product not held) per label month.

A purchase in month t = the product was not held in months t-3..t-1 and is held in t
(grill me Q9). Primary accounts (Tabungan Plus, Tabungan Plus Muda, Tabungan Plus Anak) are not recommended:
they change with age (Q18). Features use month t-1 only: KYC profile, other products held,
and the knowledge graph of month t-1 (person-product embedding similarity, PageRank).
Training months get negative sampling; the test month keeps every pair.
"""
import numpy as np
import pandas as pd

from src.config import path, settings

PRIMARY = ["prod_tabungan_plus", "prod_tabungan_plus_muda", "prod_tabungan_plus_anak"]
TABLE = ["produk", "usia", "pekerjaan", "kisaran_pendapatan", "provinsi", "perkotaan", "channel", "segmen",
         "lama_nasabah_bulan", "jumlah_produk_dipegang", "popularitas_produk"]
GRAPH = ["kemiripan_graph", "dot_graph", "pagerank"] + [f"pc_{i}" for i in range(8)]


def clean(name: str) -> pd.DataFrame:
    return pd.read_parquet(path("processed") / "clean" / f"{name}.parquet")


def build(neg_rate: float = 0.15) -> pd.DataFrame:
    cfg = settings()["windows"]
    gap = cfg["nbo_tanpa_produk_bulan"]
    panel, nas, levels = clean("nasabah_bulanan"), clean("nasabah"), clean("produk_level")
    prods = [c for c in panel.columns if c.startswith("prod_") and c not in PRIMARY]
    names = dict(zip(levels["kolom"], levels["produk"]))
    rng = np.random.default_rng(settings()["seed"])
    profile = nas.set_index("person_id")[["pekerjaan", "kisaran_pendapatan", "provinsi", "perkotaan", "channel"]]
    rows = []
    test_month = max(cfg["nbo_label_bulan"])
    for t in cfg["nbo_label_bulan"]:
        window = panel[panel["bulan_ke"].between(t - gap, t)]
        wide = window.pivot_table(index="person_id", columns="bulan_ke", values=prods, aggfunc="max")
        present = window.groupby("person_id")["bulan_ke"].nunique() == gap + 1    # customer in all months
        wide = wide[present.reindex(wide.index).fillna(False)]
        prev = panel[panel["bulan_ke"] == t - 1].set_index("person_id").loc[wide.index]
        gr = pd.read_parquet(path("processed") / "graph" / f"graph_w{t - 1}.parquet").set_index("id")
        emb_cols = [c for c in gr.columns if c.startswith("emb_")]
        P = gr.reindex(wide.index)[emb_cols].fillna(0).to_numpy()
        pnorm = np.linalg.norm(P, axis=1) + 1e-9
        # Person embedding summary: first 8 principal components of the month's person vectors.
        Pc = P - P.mean(axis=0)
        _, _, vt = np.linalg.svd(Pc[rng.choice(len(Pc), min(len(Pc), 20000), replace=False)], full_matrices=False)
        pcs = Pc @ vt[:8].T
        held_now = prev[prods].sum(axis=1).to_numpy()
        for col in prods:
            hist = wide[col].to_numpy()                      # months t-gap .. t
            free = np.nan_to_num(hist[:, :gap]).max(axis=1) == 0
            y = np.nan_to_num(hist[:, gap]) == 1
            name = names.get(col, col)
            q = gr[emb_cols].reindex([name]).fillna(0).to_numpy()[0]
            dot = P @ q
            sim = dot / (pnorm * (np.linalg.norm(q) + 1e-9))
            keep = free.copy()
            if t != test_month:                               # negative sampling for training months
                keep &= y | (rng.random(len(y)) < neg_rate)
            idx = np.flatnonzero(keep)
            if not len(idx):
                continue
            part = pd.DataFrame({"person_id": wide.index[idx], "bulan_label": t, "produk": name, "kolom": col,
                                 "label": y[idx].astype(int), "kemiripan_graph": sim[idx], "dot_graph": dot[idx],
                                 "jumlah_produk_dipegang": held_now[idx],
                                 "popularitas_produk": float(prev[col].mean())})
            for i in range(8):
                part[f"pc_{i}"] = pcs[idx, i]
            rows.append(part)
    df = pd.concat(rows, ignore_index=True)
    last = panel.set_index(["person_id", "bulan_ke"])[["usia", "segmen", "lama_nasabah_bulan"]]
    key = pd.MultiIndex.from_arrays([df["person_id"], df["bulan_label"] - 1])
    df[["usia", "segmen", "lama_nasabah_bulan"]] = last.reindex(key).to_numpy()
    df = df.join(profile, on="person_id")
    pr = {t: pd.read_parquet(path("processed") / "graph" / f"graph_w{t - 1}.parquet", columns=["id", "pagerank"]).set_index("id")["pagerank"]
          for t in cfg["nbo_label_bulan"]}
    df["pagerank"] = [pr[t].get(p, np.nan) for p, t in zip(df["person_id"], df["bulan_label"])]
    for c in ["produk", "pekerjaan", "kisaran_pendapatan", "provinsi", "channel", "segmen"]:
        df[c] = df[c].fillna("NA").astype(str).astype("category")
    dst = path("processed") / "features"
    dst.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dst / "nbo.parquet", index=False)
    return df


def topk(df: pd.DataFrame, score: str, ks=(1, 3)) -> dict:
    """Per-customer ranking metrics: Precision@k and Recall@k over customers with a purchase."""
    d = df[["person_id", "label", score]].sort_values(["person_id", score], ascending=[True, False])
    d["rank"] = d.groupby("person_id").cumcount() + 1
    buyers = d.groupby("person_id")["label"].transform("sum") > 0
    d = d[buyers]
    out = {}
    for k in ks:
        top = d[d["rank"] <= k]
        out[f"precision@{k}"] = top["label"].mean()
        out[f"recall@{k}"] = top.groupby("person_id")["label"].sum().sum() / d["label"].sum()
    return out
