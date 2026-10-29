"""Fairness audit (PRD pillar 3, POJK 22/2023 Pasal 4): recommendation rate and recall per
group, and disparate impact = lowest group rate / highest group rate (flag below 0.8).
Gender is never a model feature; it is only used here."""
import numpy as np
import pandas as pd

from src.config import path

DI_MIN = 0.8


def audit(df: pd.DataFrame, score: str, label: str, groups: list[str], top: float) -> pd.DataFrame:
    cut = df[score].quantile(1 - top)
    d = df.assign(direkomendasikan=(df[score] >= cut).astype(int))
    rows = []
    for g in groups:
        t = d.groupby(g, observed=True).agg(n=(label, "size"), base_rate=(label, "mean"),
                                            tingkat_rekomendasi=("direkomendasikan", "mean"),
                                            recall=("direkomendasikan", lambda s: s[d.loc[s.index, label] == 1].mean()))
        t = t[t["n"] >= 200]
        di = t["tingkat_rekomendasi"].min() / t["tingkat_rekomendasi"].max() if len(t) > 1 else np.nan
        # Equal opportunity: do actual buyers in every group get found equally often?
        eo = t["recall"].min() / t["recall"].max() if len(t) > 1 and t["recall"].max() > 0 else np.nan
        base_ratio = t["base_rate"].min() / t["base_rate"].max() if len(t) > 1 and t["base_rate"].max() > 0 else np.nan
        for name, r in t.iterrows():
            rows.append({"atribut": g, "kelompok": name, **r.to_dict(), "disparate_impact_atribut": di,
                         "rasio_base_rate_atribut": base_ratio, "equal_opportunity_atribut": eo,
                         "lolos_0_8": bool(di >= DI_MIN) if not np.isnan(di) else True})
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    nas = pd.read_parquet(path("processed") / "clean" / "nasabah.parquet")[["person_id", "jenis_kelamin"]]
    nbo = pd.read_parquet(path("processed") / "scores" / "nbo_test.parquet").merge(nas, on="person_id", how="left")
    nbo["kelompok_usia"] = pd.cut(nbo["usia"], [0, 25, 35, 50, 120], labels=["<=25", "26-35", "36-50", ">50"])
    nbo["jenis_kelamin"] = nbo["jenis_kelamin"].fillna("NA")
    a = audit(nbo, "skor", "label", ["jenis_kelamin", "kelompok_usia", "provinsi"], top=0.01).assign(mesin="nbo")
    acq = pd.read_parquet(path("processed") / "scores" / "akuisisi_test.parquet")
    acq["kelompok_volume"] = pd.qcut(acq["log_nominal_total"].rank(method="first"), 4, labels=["Q1 kecil", "Q2", "Q3", "Q4 besar"])
    acq["tipe_prospek"] = np.select([acq["peran_pedagang"] == 1, acq["peran_karyawan"] == 1, acq["tipe_perusahaan"] == 1],
                                    ["pedagang", "karyawan", "perusahaan"], "lainnya")
    b = audit(acq, "skor", "label", ["kelompok_volume", "tipe_prospek"], top=0.10).assign(mesin="akuisisi")
    # The app ranks prospects within their type (RM Commercial sees companies; traders and
    # employees go to anchor programmes), so the audit is repeated on that ranking.
    acq["skor_dalam_tipe"] = acq.groupby("tipe_prospek")["skor"].rank(pct=True)
    c = audit(acq, "skor_dalam_tipe", "label", ["kelompok_volume", "tipe_prospek"], top=0.10).assign(mesin="akuisisi (peringkat per tipe)")
    b = pd.concat([b, c], ignore_index=True)
    out = pd.concat([a, b], ignore_index=True)
    out.to_csv(path("outputs") / "model" / "fairness.csv", index=False)
    return out
