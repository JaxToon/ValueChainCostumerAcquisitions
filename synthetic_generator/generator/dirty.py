"""Controlled data-quality problems for output/data_bank/ (config.yaml: data_kotor).

Real bank extracts have missing values, typed-in variants, impossible values and
duplicates; the EDA rubric (Day 2) scores how the team handles them. Every change is
logged so the clean truth in kunci_evaluasi/ can prove the cleaning was right.
"""
import numpy as np
import pandas as pd

# Typed-in variants seen in manual data entry (ASUMSI: illustrative, not measured).
ABBREVIATIONS = {"Laki-Laki": "L", "Perempuan": "P", "DKI Jakarta": "Jakarta", "DI Yogyakarta": "Jogja",
                 "Pegawai/Profesional": "Pegawai", "Pengusaha/Wiraswasta": "Wiraswasta"}
VARIANTS = [str.upper, str.lower, lambda s: s + " ", lambda s: " " + s, lambda s: ABBREVIATIONS.get(s, s.upper())]
BAD_AGES = [-1, 0, 150, 999]


def apply(view: dict, cfg: dict, rng: np.random.Generator):
    if not cfg.get("aktif", False):
        return view, pd.DataFrame()
    out, log = dict(view), []
    for name, spec in cfg.items():
        if name == "aktif" or name not in out:
            continue
        df = out[name].reset_index(drop=True).copy()
        key = row_key(df)
        for col, rate in spec.get("hilang", {}).items():
            idx = pick(df, rate, rng)
            log += entries(name, col, "hilang", df, idx, key, [np.nan] * len(idx))
            df[col] = df[col].astype(object) if df[col].dtype.kind in "iub" else df[col]
            df.loc[idx, col] = np.nan
        for col, rate in spec.get("variasi_teks", {}).items():
            idx = pick(df[df[col].notna()], rate, rng)
            new = [variant(str(v), rng) for v in df.loc[idx, col]]
            log += entries(name, col, "variasi_teks", df, idx, key, new)
            df[col] = df[col].astype(object)
            df.loc[idx, col] = new
        for col, rate in spec.get("outlier", {}).items():
            idx = pick(df[df[col].notna()], rate, rng)
            if "usia" in col:
                new = rng.choice(BAD_AGES, len(idx))
            else:  # fat-finger: three extra zeros, or a sign flip
                new = df.loc[idx, col].to_numpy() * rng.choice([1000, -1], len(idx))
            log += entries(name, col, "outlier", df, idx, key, list(new))
            df[col] = df[col].astype(float)
            df.loc[idx, col] = new
        if spec.get("duplikat_baris"):
            idx = pick(df, spec["duplikat_baris"], rng)
            log += entries(name, "(baris)", "duplikat", df, idx, key, ["duplikat"] * len(idx))
            df = pd.concat([df, df.loc[idx]], ignore_index=True).sample(frac=1, random_state=int(rng.integers(1 << 31)))
            key = row_key(df.reset_index(drop=True))
        out[name] = df.reset_index(drop=True)
    return out, pd.DataFrame(log)


def variant(value: str, rng: np.random.Generator) -> str:
    """A typed-in variant that really differs from the original (upper-case codes such as
    'R,S,T,U' do not change under upper(), so fall back to a stray trailing space).
    Company names get the legal-form variants seen in transfer messages and lead files."""
    options = COMPANY_VARIANTS if value[:3] in ("PT ", "CV ") else VARIANTS
    new = options[rng.integers(len(options))](value)
    return new if new != value else value + " "


def _legal_form_last(s: str) -> str:
    form, rest = s.split(" ", 1)
    return f"{rest} {form}"


# ASUMSI: illustrative spellings, e.g. "PT Mitra 0001" -> "PT. Mitra 0001", "MITRA 0001 PT".
COMPANY_VARIANTS = [str.upper, lambda s: s.replace(" ", ". ", 1), _legal_form_last,
                    lambda s: _legal_form_last(s).upper(), lambda s: s.split(" ", 1)[1],
                    lambda s: s + " Tbk" if s.startswith("PT ") else s.replace(" ", ".", 1)]


def pick(df: pd.DataFrame, rate: float, rng: np.random.Generator) -> np.ndarray:
    n = int(round(len(df) * rate))
    return rng.choice(df.index.to_numpy(), size=min(n, len(df)), replace=False)


def row_key(df: pd.DataFrame) -> pd.Series:
    """Readable row identifier for the log: entity id, plus month for monthly tables."""
    if "from_id" in df.columns:
        return df["bulan_ke"].astype(str) + "|" + df["from_id"] + "|" + df["to_id"]
    if "counterparty_id" in df.columns:
        return df["bulan_ke"].astype(str) + "|" + df["company_id"] + "|" + df["counterparty_id"] + "|" + df["arah"]
    idcol = next(c for c in ["person_id", "company_id", "entity_id", "lead_id"] if c in df.columns)
    return df[idcol] + ("|" + df["bulan_ke"].astype(str) if "bulan_ke" in df.columns else "")


def entries(name, col, kind, df, idx, key, new):
    original = df.loc[idx, col].tolist() if col in df.columns else [""] * len(idx)
    return [{"file": name, "kolom": col, "jenis": kind, "id": i, "nilai_asli": o, "nilai_kotor": n}
            for i, o, n in zip(key.loc[idx].tolist(), original, new)]
