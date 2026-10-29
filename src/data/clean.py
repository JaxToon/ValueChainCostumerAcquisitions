"""Load output/data_bank (what a bank can really see) and clean the planted data-quality
problems: duplicates, typed-in variants, impossible values, missing values, and company
names that must be matched by name (entity resolution). Writes data/processed/clean/*.parquet.

Only data_bank is used here. kunci_evaluasi/catatan_data_kotor.csv is read by
evaluate_cleaning() to score the cleaning for the EDA slides, never to clean.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import ROOT, path, settings

GENDERS = ["Laki-Laki", "Perempuan"]
OCCUPATIONS = ["Pegawai/Profesional", "Pengusaha/Wiraswasta", "Pensiunan/Purnawirawan",
               "Petani/Peternak/Pekebun/Nelayan", "Pekerjaan Lainnya", "Pelajar/Mahasiswa",
               "Ibu Rumah Tangga", "Tidak/Belum Pernah Bekerja"]
# Typed-in short forms seen in manual entry -> canonical value.
ABBREVIATIONS = {"l": "Laki-Laki", "p": "Perempuan", "jakarta": "DKI Jakarta", "jogja": "DI Yogyakarta",
                 "pegawai": "Pegawai/Profesional", "wiraswasta": "Pengusaha/Wiraswasta"}
LEGAL_FORMS = {"pt", "cv", "tbk"}


def read(name: str) -> pd.DataFrame:
    p = path("raw") / name
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p, low_memory=False)


def canonical(values: pd.Series, allowed: list[str]) -> pd.Series:
    """Map variants (case, spaces, short forms) onto the allowed spellings; unknown -> NaN."""
    lookup = {a.casefold(): a for a in allowed}
    lookup.update({k: v for k, v in ABBREVIATIONS.items() if v in allowed})
    key = values.astype("string").str.strip().str.casefold()
    return key.map(lookup).astype(object).where(values.notna(), np.nan)


def name_key(names: pd.Series) -> pd.Series:
    """Company name without legal form, punctuation, case or spacing: 'PT. Mitra 0001',
    'MITRA 0001 PT' and 'Mitra 0001' all become 'mitra 0001'."""
    s = names.astype("string").str.casefold().str.replace(r"[^\w\s]", " ", regex=True)
    return s.map(lambda x: " ".join(t for t in x.split() if t not in LEGAL_FORMS) if isinstance(x, str) else pd.NA)


def fix_amount(amount: pd.Series, group: pd.Series, k: float) -> pd.Series:
    """Negative -> absolute value; more than k x the group's median -> divided by 1000
    (the planted fat-finger error adds three zeros)."""
    a = amount.abs()
    med = a.groupby(group).transform("median")
    return a.where(~(a > k * med), a / 1000)


def provinces() -> list[str]:
    return pd.read_csv(ROOT / "synthetic_generator" / "reference" / "bps_penduduk_provinsi_2026.csv")["provinsi"].tolist()


def sectors() -> list[str]:
    return pd.read_csv(ROOT / "synthetic_generator" / "reference" / "bps_pekerja_sektor_2025.csv")["kode_kbli"].astype(str).tolist()


def clean_all() -> dict[str, pd.DataFrame]:
    cfg = settings()["cleaning"]
    prov, sect = provinces(), sectors()
    out = {}

    n = read("nasabah.csv").drop_duplicates()
    n = n.drop_duplicates("person_id", keep="first")
    n["provinsi"] = canonical(n["provinsi"], prov)
    n["jenis_kelamin"] = canonical(n["jenis_kelamin"], GENDERS)
    n["pekerjaan"] = canonical(n["pekerjaan"], OCCUPATIONS)
    n.loc[~n["usia_bulan1"].between(cfg["usia_min"], cfg["usia_max"]), "usia_bulan1"] = np.nan
    out["nasabah"] = n

    m = read("nasabah_bulanan.parquet").drop_duplicates(["person_id", "bulan_ke"]).sort_values(["person_id", "bulan_ke"])
    m.loc[~m["usia"].between(cfg["usia_min"], cfg["usia_max"]), "usia"] = np.nan
    g = m.groupby("person_id")
    m["usia"] = g["usia"].transform(lambda s: s.ffill().bfill())
    prod = [c for c in m.columns if c.startswith("prod_")]
    m[prod] = g[prod].ffill().fillna(0).astype("int8")
    m["segmen"] = g["segmen"].transform(lambda s: s.ffill().bfill())
    out["nasabah_bulanan"] = m.reset_index(drop=True)

    c = read("companies.csv").drop_duplicates("company_id")
    c["provinsi"] = canonical(c["provinsi"], prov)
    c["sektor"] = canonical(c["sektor"].astype(str).where(c["sektor"].notna()), sect)
    out["companies"] = c

    p = read("persons.csv").drop_duplicates("person_id")
    p["provinsi"] = canonical(p["provinsi"], prov)
    p["jenis_kelamin"] = canonical(p["jenis_kelamin"], GENDERS)
    p["pekerjaan"] = canonical(p["pekerjaan"], OCCUPATIONS)
    out["persons"] = p

    t = read("transfers_monthly.csv").drop_duplicates()
    t = t.drop_duplicates(["bulan_ke", "from_id", "to_id"])
    pair = t["from_id"] + "|" + t["to_id"]
    t["total_nominal_rp"] = fix_amount(t["total_nominal_rp"], pair, cfg["outlier_kali_median"])
    t["jumlah_transaksi"] = t["jumlah_transaksi"].fillna(t.groupby(pair)["jumlah_transaksi"].transform("median")).fillna(1)
    out["transfers"] = t.reset_index(drop=True)

    x = read("transaksi_counterparty_bulanan.csv").drop_duplicates(["bulan_ke", "company_id", "counterparty_id", "arah"])
    x["counterparty_nama_kunci"] = name_key(x["counterparty_nama"])
    out["transaksi_counterparty"] = x.reset_index(drop=True)

    s = read("saldo_bulanan.csv").drop_duplicates(["company_id", "bulan_ke"])
    s["saldo_rata2_rp"] = fix_amount(s["saldo_rata2_rp"], s["company_id"], cfg["outlier_kali_median"])
    ratio = (s["saldo_akhir_bulan_rp"] / s["saldo_rata2_rp"]).median()
    s["saldo_akhir_bulan_rp"] = s["saldo_akhir_bulan_rp"].fillna(s["saldo_rata2_rp"] * ratio)
    out["saldo"] = s.reset_index(drop=True)

    leads = read("lead_bisdev.csv").drop_duplicates()
    leads = leads.drop_duplicates("lead_id")
    keys = c.assign(k=name_key(c["nama_samaran"])).drop_duplicates("k").set_index("k")["company_id"]
    leads["company_id_cocok"] = name_key(leads["nama_perusahaan"]).map(keys)
    leads["anchor_id_cocok"] = name_key(leads["anchor_terkait"]).map(keys)
    out["lead_bisdev"] = leads

    for name in ["employment.csv", "acquisitions.csv", "rm_portofolio.csv", "riwayat_produk_wholesale.csv",
                 "fasilitas_pembiayaan.csv", "label_wholesale.csv", "produk_level.csv"]:
        out[Path(name).stem] = read(name)

    dst = path("processed") / "clean"
    dst.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        df.to_parquet(dst / f"{name}.parquet", index=False)
    return out


def evaluate_cleaning(clean: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Score the cleaning against the full truth in kunci_evaluasi (evaluation only):
    share of cells equal to the truth, and what is still missing."""
    truth = path("truth")
    rows = []

    def compare(name, df, key, truth_df, cols):
        m = df.merge(truth_df[key + cols], on=key, suffixes=("", "_asli"))
        for col in cols:
            ok = m[col].notna()
            a, b = m.loc[ok, col], m.loc[ok, f"{col}_asli"]
            if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                same = np.isclose(a.astype(float), b.astype(float)).mean()
            else:
                same = (a.astype(str) == b.astype(str)).mean()
            rows.append({"file": name, "kolom": col, "baris": len(m), "sama_dengan_asli": round(same, 4),
                         "masih_kosong": round(1 - ok.mean(), 4)})

    nas = pd.read_csv(truth / "nasabah_lengkap.csv")
    compare("nasabah", clean["nasabah"], ["person_id"], nas, ["provinsi", "jenis_kelamin", "pekerjaan", "usia_bulan1"])
    rows.append({"file": "nasabah", "kolom": "(duplikat)", "baris": len(clean["nasabah"]),
                 "sama_dengan_asli": float(clean["nasabah"]["person_id"].is_unique), "masih_kosong": 0.0})
    comp = pd.read_csv(truth / "companies_lengkap.csv")
    compare("companies", clean["companies"], ["company_id"], comp, ["provinsi", "sektor"])
    tr = pd.read_csv(truth / "transfers_lengkap.csv")
    t = clean["transfers"].merge(tr, on=["bulan_ke", "from_id", "to_id"], suffixes=("", "_asli"))
    rows.append({"file": "transfers", "kolom": "total_nominal_rp", "baris": len(t),
                 "sama_dengan_asli": round(float(np.isclose(t["total_nominal_rp"], t["total_nominal_rp_asli"], rtol=0.01).mean()), 4),
                 "masih_kosong": 0.0})
    lm = clean["lead_bisdev"].merge(pd.read_csv(truth / "lead_bisdev_kunci.csv"), on="lead_id")
    rows.append({"file": "lead_bisdev", "kolom": "company_id (entity resolution)", "baris": len(lm),
                 "sama_dengan_asli": round(float((lm["company_id_cocok"] == lm["company_id"]).mean()), 4),
                 "masih_kosong": round(float(lm["company_id_cocok"].isna().mean()), 4)})
    return pd.DataFrame(rows)
