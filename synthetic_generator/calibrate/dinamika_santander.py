"""Measure real monthly product behaviour from the Santander panel.

Indonesia has no public data on how often bank customers open or close a product
each month, or which products are held together. Santander is the only real
monthly panel we have, so we take its *shape* (monthly churn, how propensity moves
with age and income rank, co-ownership correlation, customer entry and exit) and
let the generator set ownership *levels* from Indonesian sources.

Output (reference/):
  dinamika_produk_santander.csv   per Santander product: level, monthly acquisition and churn
  rr_umur_santander.csv           relative holding rate per age band (1.0 = product average)
  rr_pendapatan_santander.csv     relative holding rate per income quintile within province
  korelasi_produk_santander.csv   latent correlation between products (tetrachoric approximation)
  dinamika_nasabah_santander.csv  monthly share of customers entering and leaving the panel
  santander_tambahan.csv          single numbers: median entry/exit rate, TOP segment share,
                                  tenure quantiles (months)

Run once (reads train.csv; ~3-5 minutes):
  python calibrate/dinamika_santander.py --train ../Data/train.csv --sample 200000
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "reference"

PRODUCTS = [
    "ind_ahor_fin_ult1", "ind_aval_fin_ult1", "ind_cco_fin_ult1", "ind_cder_fin_ult1",
    "ind_cno_fin_ult1", "ind_ctju_fin_ult1", "ind_ctma_fin_ult1", "ind_ctop_fin_ult1",
    "ind_ctpp_fin_ult1", "ind_deco_fin_ult1", "ind_deme_fin_ult1", "ind_dela_fin_ult1",
    "ind_ecue_fin_ult1", "ind_fond_fin_ult1", "ind_hip_fin_ult1", "ind_plan_fin_ult1",
    "ind_pres_fin_ult1", "ind_reca_fin_ult1", "ind_tjcr_fin_ult1", "ind_valo_fin_ult1",
    "ind_viv_fin_ult1", "ind_nomina_ult1", "ind_nom_pens_ult1", "ind_recibo_ult1",
]
# Same bands as OJK SNLIK 2025, so the shape can be applied to Indonesian age groups.
AGE_BINS = [14, 17, 25, 35, 50, 79]
AGE_LABELS = ["15-17", "18-25", "26-35", "36-50", "51-79"]


def load(train: Path, sample: int, seed: int) -> pd.DataFrame:
    cols = ["fecha_dato", "ncodpers", "age", "nomprov", "renta", "segmento", "antiguedad"] + PRODUCTS
    ids = pd.read_csv(train, usecols=["ncodpers"])["ncodpers"].dropna().astype(np.int64).unique()
    keep = set(np.random.default_rng(seed).choice(ids, size=min(sample, len(ids)), replace=False).tolist())
    parts = []
    for chunk in pd.read_csv(train, usecols=cols, chunksize=1_000_000, low_memory=False):
        chunk = chunk.dropna(subset=["ncodpers"])
        parts.append(chunk[chunk["ncodpers"].astype(np.int64).isin(keep)])
    df = pd.concat(parts, ignore_index=True)
    df["ncodpers"] = df["ncodpers"].astype(np.int64)
    df["age"] = pd.to_numeric(df["age"].astype(str).str.strip(), errors="coerce")
    df["renta"] = pd.to_numeric(df["renta"], errors="coerce")
    df[PRODUCTS] = df[PRODUCTS].apply(pd.to_numeric, errors="coerce").fillna(0).astype(np.int8)
    d = pd.to_datetime(df["fecha_dato"])
    df["month"] = (d.dt.year * 12 + d.dt.month).astype(np.int32)
    return df.sort_values(["ncodpers", "month"]).reset_index(drop=True)


def transitions(df: pd.DataFrame) -> pd.DataFrame:
    # Only consecutive months of the same customer count as a transition.
    prev = df.groupby("ncodpers")[PRODUCTS].shift(1)
    gap = df.groupby("ncodpers")["month"].shift(1)
    ok = (df["month"] - gap) == 1
    rows = []
    for p in PRODUCTS:
        before, now = prev.loc[ok, p], df.loc[ok, p]
        non_holders, holders = (before == 0), (before == 1)
        rows.append({
            "kolom_santander": p,
            "level": df[p].mean(),
            "akuisisi_bulanan": ((now == 1) & non_holders).sum() / max(non_holders.sum(), 1),
            "churn_bulanan": ((now == 0) & holders).sum() / max(holders.sum(), 1),
            "n_pemegang": int(holders.sum()),
        })
    return pd.DataFrame(rows)


def relative_rates(df: pd.DataFrame, key: str) -> pd.DataFrame:
    g = df.groupby(key, observed=True)[PRODUCTS].mean()
    rr = g / df[PRODUCTS].mean().replace(0, np.nan)
    return rr.fillna(1.0).round(4).T.rename_axis("kolom_santander").reset_index()


def latent_correlation(df: pd.DataFrame) -> pd.DataFrame:
    # Greiner's relation r = sin(pi/2 * phi) approximates the latent (tetrachoric)
    # correlation from the binary phi coefficient; good enough to keep co-ownership.
    last = df.groupby("ncodpers").tail(1)[PRODUCTS]
    phi = last.corr().fillna(0.0)
    lat = np.sin(np.pi / 2 * phi.to_numpy())
    np.fill_diagonal(lat, 1.0)
    return pd.DataFrame(lat, index=PRODUCTS, columns=PRODUCTS).round(4)


def customer_flow(df: pd.DataFrame) -> pd.DataFrame:
    first = df.groupby("ncodpers")["month"].min().value_counts().sort_index()
    last = df.groupby("ncodpers")["month"].max().value_counts().sort_index()
    active = df.groupby("month")["ncodpers"].nunique()
    out = pd.DataFrame({"aktif": active, "masuk": first, "keluar": last}).fillna(0)
    out["laju_masuk"] = out["masuk"] / out["aktif"]
    out["laju_keluar"] = out["keluar"] / out["aktif"]
    # The first month's "entries" and last month's "exits" are panel edges, not behaviour.
    out.loc[out.index.min(), ["laju_masuk"]] = np.nan
    out.loc[out.index.max(), ["laju_keluar"]] = np.nan
    return out.reset_index(names="bulan").round(5)


def extra_numbers(df: pd.DataFrame, flow: pd.DataFrame) -> pd.DataFrame:
    last = df.groupby("ncodpers").tail(1)
    tenure = pd.to_numeric(last["antiguedad"].astype(str).str.strip(), errors="coerce")
    tenure = tenure[tenure >= 0]
    # Median, not mean: one month (2015-07) adds ~23% customers at once, a panel
    # expansion in the source data rather than customer behaviour.
    rows = [
        ("laju_masuk_bulanan_median", flow["laju_masuk"].median()),
        ("laju_keluar_bulanan_median", flow["laju_keluar"].median()),
        ("porsi_segmen_top", (last["segmento"].astype(str).str.strip() == "01 - TOP").mean()),
    ]
    rows += [(f"lama_nasabah_bulan_p{q}", tenure.quantile(q / 100)) for q in range(0, 101, 5)]
    return pd.DataFrame(rows, columns=["indikator", "nilai"]).round(6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, required=True)
    ap.add_argument("--sample", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    df = load(args.train, args.sample, args.seed)
    print(f"Rows {len(df):,}, customers {df['ncodpers'].nunique():,}")

    adults = df[df["age"].between(15, 79)].copy()
    adults["kelompok_umur"] = pd.cut(adults["age"], AGE_BINS, labels=AGE_LABELS)
    # Income rank inside each province, so regional income levels do not leak into the shape.
    inc = adults.dropna(subset=["renta"]).copy()
    inc["kuintil_pendapatan"] = inc.groupby("nomprov")["renta"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"]))

    OUT.mkdir(exist_ok=True)
    transitions(df).round(6).to_csv(OUT / "dinamika_produk_santander.csv", index=False)
    relative_rates(adults, "kelompok_umur").to_csv(OUT / "rr_umur_santander.csv", index=False)
    relative_rates(inc, "kuintil_pendapatan").to_csv(OUT / "rr_pendapatan_santander.csv", index=False)
    latent_correlation(df).to_csv(OUT / "korelasi_produk_santander.csv")
    flow = customer_flow(df)
    flow.to_csv(OUT / "dinamika_nasabah_santander.csv", index=False)
    extra_numbers(df, flow).to_csv(OUT / "santander_tambahan.csv", index=False)
    print(f"Written to {OUT}")


if __name__ == "__main__":
    main()
