"""Features for the wholesale engine (F19, F20): one row per Bank company per window.

Everything comes from what the bank sees by the feature month `last`: counterparty
transactions (with the name x bank class), balances, product history, facilities, the
company's own KYC (segment, sector, age) and graph outputs. Each label has its own pool
of companies that could still get it in that window.
"""
import numpy as np
import pandas as pd

from src.config import path, settings

LABELS = ["cross_sell_wholesale", "non_debitur_ke_debitur", "reaktivasi", "leakage"]
TABLE = ["segmen_bank", "sektor", "umur_usaha", "is_anchor", "log_saldo_rata2", "tren_saldo_3bln",
         "jumlah_produk_aktif", "punya_fasilitas", "log_plafon", "punya_trade_selesai", "bulan_sejak_trade_selesai"]
GRAPH = ["log_masuk", "log_keluar", "n_pembayar", "n_penerima", "porsi_ke_rekening_sendiri_bank_lain",
         "tren_porsi_rekening_sendiri", "porsi_counterparty_bank_lain", "counterparty_baru_3bln",
         "transaksi_dengan_anchor_bank", "pagerank", "porsi_bank_komunitas", "mirip_debitur", "mirip_pengguna_trade"]


def clean(name: str) -> pd.DataFrame:
    return pd.read_parquet(path("processed") / "clean" / f"{name}.parquet")


def month_index(d: pd.Series) -> pd.Series:
    d = pd.to_datetime(d, errors="coerce")
    return ((d.dt.year - 2025) * 12 + d.dt.month).fillna(999).astype(int)


def build_window(k: int, last: int, emb_dim: int = 64) -> pd.DataFrame:
    comp = clean("companies")
    own_cust = comp[comp["is_bank_customer"] == 1].set_index("company_id")
    tx, sal = clean("transaksi_counterparty"), clean("saldo")
    hist, fac, lab = clean("riwayat_produk_wholesale"), clean("fasilitas_pembiayaan"), clean("label_wholesale")
    f = pd.DataFrame(index=own_cust.index)

    lookback = settings()["windows"]["lookback_bulan"]
    hist_tx = tx[tx["bulan_ke"] <= last]                       # for "first seen" only
    w = hist_tx[hist_tx["bulan_ke"] > last - lookback]
    other = w[w["counterparty_id"] != w["company_id"]]
    f["log_masuk"] = np.log1p(other[other["arah"] == "MASUK"].groupby("company_id")["total_nominal_rp"].sum())
    f["log_keluar"] = np.log1p(other[other["arah"] == "KELUAR"].groupby("company_id")["total_nominal_rp"].sum())
    f["n_pembayar"] = other[other["arah"] == "MASUK"].groupby("company_id")["counterparty_id"].nunique()
    f["n_penerima"] = other[other["arah"] == "KELUAR"].groupby("company_id")["counterparty_id"].nunique()
    out_all = w[w["arah"] == "KELUAR"]

    def own_share(x):
        tot = x.groupby("company_id")["total_nominal_rp"].sum()
        own = x[x["kelas_nama_bank"] == "NAMA_SAMA_BANK_BEDA"].groupby("company_id")["total_nominal_rp"].sum()
        return (own / tot).fillna(0)

    f["porsi_ke_rekening_sendiri_bank_lain"] = own_share(out_all)
    f["tren_porsi_rekening_sendiri"] = (own_share(out_all[out_all["bulan_ke"] > last - 3]).reindex(f.index).fillna(0)
                                        - own_share(out_all[out_all["bulan_ke"] <= last - 3]).reindex(f.index).fillna(0))
    f["porsi_counterparty_bank_lain"] = other.assign(beda=other["counterparty_bank"] != "Bank").groupby("company_id")["beda"].mean()
    ho = hist_tx[hist_tx["counterparty_id"] != hist_tx["company_id"]]
    first_seen = ho.groupby(["company_id", "counterparty_id"])["bulan_ke"].min().reset_index()
    f["counterparty_baru_3bln"] = first_seen[first_seen["bulan_ke"] > last - 3].groupby("company_id").size()
    anchors = set(comp.loc[comp["is_anchor"].astype(bool) & (comp["is_bank_customer"] == 1), "company_id"])
    f["transaksi_dengan_anchor_bank"] = other[other["counterparty_id"].isin(anchors)].groupby("company_id")["jumlah_transaksi"].sum()

    s = sal[sal["bulan_ke"] <= last]
    f["log_saldo_rata2"] = np.log1p(s[s["bulan_ke"] > last - 3].groupby("company_id")["saldo_rata2_rp"].mean())
    prev = np.log1p(s[(s["bulan_ke"] <= last - 3) & (s["bulan_ke"] > last - 6)].groupby("company_id")["saldo_rata2_rp"].mean())
    f["tren_saldo_3bln"] = f["log_saldo_rata2"] - prev.reindex(f.index)

    h = hist.assign(mulai=month_index(hist["tanggal_mulai"]), selesai=month_index(hist["tanggal_selesai"]))
    h = h[h["mulai"] <= last]
    active = h[h["selesai"] > last]
    f["jumlah_produk_aktif"] = active.groupby("company_id").size()
    ended = h[(h["jenis"] == "transaksi") & (h["selesai"] <= last)]
    f["punya_trade_selesai"] = ended.groupby("company_id").size().clip(upper=1)
    f["bulan_sejak_trade_selesai"] = last - ended.groupby("company_id")["selesai"].max()
    fa = fac.assign(mulai=month_index(fac["tanggal_mulai"]))
    fa = fa[fa["mulai"] <= last]
    f["punya_fasilitas"] = fa.groupby("company_id").size().clip(upper=1)
    f["log_plafon"] = np.log1p(fa.groupby("company_id")["plafon_rp"].sum())

    f["segmen_bank"] = own_cust["segmen_bank"].astype(str)
    f["sektor"] = own_cust["sektor"].astype(str)
    f["umur_usaha"] = 2025 + (last - 1) // 12 - own_cust["tahun_berdiri"]
    f["is_anchor"] = own_cust["is_anchor"].astype(int)

    gr = pd.read_parquet(path("processed") / "graph" / f"graph_w{last}.parquet").set_index("id")
    isbank = set(comp.loc[comp["is_bank_customer"] == 1, "company_id"]) | set(clean("persons").query("is_bank_customer == 1")["person_id"])
    share = gr.assign(b=gr.index.isin(isbank)).groupby("komunitas")["b"].mean()
    f["pagerank"] = gr["pagerank"].reindex(f.index)
    f["porsi_bank_komunitas"] = gr["komunitas"].map(share).reindex(f.index)
    # Rotation-free graph similarity (raw FastRP coordinates differ between windows).
    E = gr[[f"emb_{d}" for d in range(emb_dim)]]
    U = E.div(np.linalg.norm(E.to_numpy(), axis=1) + 1e-9, axis=0)
    for col, ids in [("mirip_debitur", set(fa["company_id"])), ("mirip_pengguna_trade", set(h.loc[h["jenis"] == "transaksi", "company_id"]))]:
        ref_ids = U.index.intersection(pd.Index(list(ids)))
        ref = U.loc[ref_ids].mean().to_numpy() if len(ref_ids) else np.zeros(U.shape[1])
        f[col] = pd.Series(U.to_numpy() @ (ref / (np.linalg.norm(ref) + 1e-9)), index=U.index).reindex(f.index)
    f = f.join(E, how="left")
    counts = ["log_masuk", "log_keluar", "n_pembayar", "n_penerima", "porsi_ke_rekening_sendiri_bank_lain",
              "counterparty_baru_3bln", "transaksi_dengan_anchor_bank", "jumlah_produk_aktif", "punya_trade_selesai",
              "punya_fasilitas", "log_plafon", "porsi_counterparty_bank_lain"]
    f[counts] = f[counts].fillna(0)
    f["bulan_sejak_trade_selesai"] = f["bulan_sejak_trade_selesai"].fillna(-1)

    # Pools: who could still get each label in this window, using only what is known by `last`.
    before = lab[lab["jendela"] < k]
    seen_own = set(w.loc[w["kelas_nama_bank"] == "NAMA_SAMA_BANK_BEDA", "company_id"])
    pools = {"cross_sell_wholesale": pd.Series(True, index=f.index),
             "non_debitur_ke_debitur": f["punya_fasilitas"] == 0,
             "reaktivasi": (f["punya_trade_selesai"] == 1) & ~f.index.isin(before.loc[before["label"] == "reaktivasi", "company_id"]),
             "leakage": f.index.isin(seen_own) & ~f.index.isin(before.loc[before["label"] == "leakage", "company_id"])}
    now = lab[lab["jendela"] == k]
    for name in LABELS:
        f[f"pool_{name}"] = pools[name].astype(int)
        f[f"label_{name}"] = f.index.isin(now.loc[now["label"] == name, "company_id"]).astype(int)
    f["jendela_k"], f["bulan_fitur_terakhir"] = k, last
    return f.rename_axis("company_id").reset_index()


def build_all() -> pd.DataFrame:
    w = settings()["windows"]["wholesale"]
    df = pd.concat([build_window(k, a) for k, (a, _) in enumerate(w, start=1)], ignore_index=True)
    dst = path("processed") / "features"
    dst.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dst / "wholesale.parquet", index=False)
    return df
