"""F19 transaction signals for every Bank company at the latest month (thresholds: grill me Q25).

- counterpart_baru: first seen in the last 3 months with >= Rp100 juta in a month
- counterpart_berulang: seen in >= 3 of the last 6 months
- transaksi_besar: row in the company's top 5% by amount in the last 3 months
- pindah_bank: share of money to the company's own account at another bank (NAMA_SAMA_BANK_BEDA)
  in the last month is >= 20 points above its average of the 3 months before
- counterparty_ganti_bank: a counterparty's bank in the last month differs from earlier months
"""
import pandas as pd

from src.config import path, settings

BARU_MIN = 100_000_000
BERULANG_MIN = 3
NAIK_POIN = 0.20


def build() -> pd.DataFrame:
    tx = pd.read_parquet(path("processed") / "clean" / "transaksi_counterparty.parquet")
    T = settings()["bulan"]
    other = tx[tx["counterparty_id"] != tx["company_id"]]
    rows = []

    first = other.groupby(["company_id", "counterparty_id"])["bulan_ke"].min().rename("pertama")
    recent = other[other["bulan_ke"] > T - 3]
    big = recent.groupby(["company_id", "counterparty_id"])["total_nominal_rp"].max().rename("maks")
    new = pd.concat([first, big], axis=1).dropna()
    new = new[(new["pertama"] > T - 3) & (new["maks"] >= BARU_MIN)].reset_index()
    rows.append(new.assign(sinyal="counterpart_baru", nilai=new["maks"], bulan=new["pertama"]))

    last6 = other[other["bulan_ke"] > T - 6].groupby(["company_id", "counterparty_id"])["bulan_ke"].nunique().rename("bulan_muncul")
    rep = last6[last6 >= BERULANG_MIN].reset_index()
    rows.append(rep.assign(sinyal="counterpart_berulang", nilai=rep["bulan_muncul"], bulan=T))

    q = recent.groupby("company_id")["total_nominal_rp"].transform(lambda s: s.quantile(0.95))
    top = recent[recent["total_nominal_rp"] >= q]
    rows.append(top[["company_id", "counterparty_id"]].assign(sinyal="transaksi_besar", nilai=top["total_nominal_rp"].to_numpy(),
                                                              bulan=top["bulan_ke"].to_numpy()))

    out = tx[(tx["arah"] == "KELUAR") & (tx["bulan_ke"] > T - 4)]
    tot = out.groupby(["company_id", "bulan_ke"])["total_nominal_rp"].sum()
    own = out[out["kelas_nama_bank"] == "NAMA_SAMA_BANK_BEDA"].groupby(["company_id", "bulan_ke"])["total_nominal_rp"].sum()
    share = (own / tot).fillna(0).unstack(fill_value=0)
    if T in share.columns:
        before = share[[c for c in share.columns if c < T]].mean(axis=1)
        jump = (share[T] - before)
        sw = jump[jump >= NAIK_POIN].reset_index().rename(columns={0: "nilai"})
        sw.columns = ["company_id", "nilai"]
        rows.append(sw.assign(sinyal="pindah_bank", counterparty_id=sw["company_id"], bulan=T))

    b = other.groupby(["company_id", "counterparty_id", "bulan_ke"])["counterparty_bank"].first().reset_index()
    prev = b[b["bulan_ke"] < T].groupby(["company_id", "counterparty_id"])["counterparty_bank"].agg(lambda s: s.mode().iloc[0])
    now = b[b["bulan_ke"] == T].set_index(["company_id", "counterparty_id"])["counterparty_bank"]
    both = pd.concat([prev.rename("sebelum"), now.rename("sekarang")], axis=1).dropna()
    ch = both[both["sebelum"] != both["sekarang"]].reset_index()
    rows.append(ch.assign(sinyal="counterparty_ganti_bank", nilai=1.0, bulan=T))

    sig = pd.concat(rows, ignore_index=True)[["company_id", "counterparty_id", "sinyal", "nilai", "bulan"]]
    names = tx.drop_duplicates("counterparty_id").set_index("counterparty_id")[["counterparty_nama_kunci", "counterparty_bank"]]
    sig = sig.join(names, on="counterparty_id")
    dst = path("processed") / "signals"
    dst.mkdir(parents=True, exist_ok=True)
    sig.to_parquet(dst / "sinyal_f19.parquet", index=False)
    return sig


if __name__ == "__main__":
    s = build()
    print(s["sinyal"].value_counts())
