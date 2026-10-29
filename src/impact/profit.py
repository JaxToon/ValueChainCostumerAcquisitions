"""Business impact (F12): estimated clean profit and potential loss on the test window,
for the model and the business baseline, from docs/asumsi_f12.csv (PROKSI/ASUMSI).

Clean profit = sum of value of correct picks - number contacted x contact cost.
Potential loss: wasted effort (wrong picks x cost), missed opportunity (buyers not picked x
value), and mis-selling prevented (recommendations blocked by the guardrail x cost).
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from src.config import ROOT, path

PRODUCT_VALUE = {"Bank Giro": "nilai_giro_perorangan", "Bank Deposito": "nilai_deposito_perorangan", "Mobile Banking": "nilai_mobile",
                 "Bank Payroll": "nilai_payroll_perorangan", "Bank Visa Platinum": "nilai_visa_platinum", "KPR Pembelian": "nilai_kpr",
                 "Bank Fleksi": "nilai_fleksi", "DPLK Pensiun": "nilai_dplk", "Reksa Dana (agen penjual)": "nilai_reksa_dana_bonds",
                 "Bonds": "nilai_reksa_dana_bonds", "Autodebit": "nilai_autodebit", "Prioritas": "nilai_prioritas"}


@lru_cache
def assumptions() -> dict:
    a = pd.read_csv(ROOT / "docs" / "asumsi_f12.csv")
    return dict(zip(a["parameter"], a["nilai"].astype(float)))


def values(engine: str, df: pd.DataFrame, p: dict) -> tuple[np.ndarray, np.ndarray]:
    """(value if converted, contact cost) per row, in Rp."""
    if engine == "nbo":
        v = df["produk"].astype(str).map(lambda x: p.get(PRODUCT_VALUE.get(x, ""), 0.0)).to_numpy(float)
        return v, np.full(len(df), p["biaya_kontak_ritel"])
    if engine.startswith("akuisisi"):
        tipe = df["tipe_prospek"].astype(str).to_numpy()
        monthly = np.expm1(df["log_nominal_total"].to_numpy())             # visible monthly flow
        # Expected balance = visible monthly flow x cash days / 30; value = balance x fund spread + CIB fee.
        company = (monthly * p["hari_kas_prospek"] / 30 * p["spread_dana"] + p["fee_cib"]) * p["porsi_wallet_tahun_pertama"]
        v = np.select([tipe == "perusahaan", tipe == "pedagang", tipe == "karyawan"],
                      [company, p["nilai_tabungan_plus_bisnis"] + 0.3 * p["fee_qris"], p["nilai_tabungan_plus"] + p["nilai_payroll_perorangan"]], p["nilai_tabungan_plus"])
        cost = np.select([tipe == "perusahaan", tipe == "pedagang"], [p["biaya_kunjungan_rm_wholesale"], p["biaya_kontak_pedagang"]],
                         p["biaya_kontak_ritel"])
        return v, cost
    # wholesale cross-sell: average annual fee of a transaction-banking product (ASUMSI)
    v = np.full(len(df), (p["fee_cib"] + p["fee_virtual_account"]) / 2)
    return v, np.full(len(df), p["biaya_kunjungan_rm_wholesale"])


def evaluate(engine: str, n_contact: int, score: str = "skor", skenario: float = 1.0, makro: float = 1.0,
             overrides: dict | None = None) -> dict:
    p = {**assumptions(), **(overrides or {})}
    df = pd.read_parquet(path("processed") / "scores" / f"{engine}_test.parquet")
    v, cost = values(engine, df, p)
    # "nilai_harapan": calibrated probability x value - contact cost (needs a calibrated model).
    rank = df["skor"].to_numpy() * v - cost if score == "nilai_harapan" else df[score].to_numpy()
    order = np.argsort(-rank)
    pick = np.zeros(len(df), bool)
    pick[order[:n_contact]] = True
    y = df["label"].to_numpy() == 1
    gain = skenario * makro
    gross = float((v * (pick & y)).sum() * gain)
    spend = float((cost * pick).sum())
    return {"dihubungi": int(pick.sum()), "konversi": int((pick & y).sum()), "pendapatan_kotor": gross, "biaya": spend,
            "profit_bersih": gross - spend, "rugi_usaha_sia_sia": float((cost * (pick & ~y)).sum()),
            "rugi_peluang_terlewat": float((v * (~pick & y)).sum() * gain)}


def cumulative(engine: str, score: str = "nilai_harapan", skenario: float = 1.0, makro: float = 1.0,
               overrides: dict | None = None, points: int = 400) -> pd.DataFrame:
    """Revenue and contact cost when the top n are contacted, for every n (same ranking as
    evaluate), thinned to about `points` rows plus the n with the widest revenue-cost gap."""
    p = {**assumptions(), **(overrides or {})}
    df = pd.read_parquet(path("processed") / "scores" / f"{engine}_test.parquet")
    v, cost = values(engine, df, p)
    rank = df["skor"].to_numpy() * v - cost if score == "nilai_harapan" else df[score].to_numpy()
    order = np.argsort(-rank)
    y = df["label"].to_numpy()[order] == 1
    gross = np.cumsum(v[order] * y) * skenario * makro
    spend = np.cumsum(cost[order])
    profit = gross - spend
    best = int(np.argmax(profit))
    idx = np.unique(np.r_[np.linspace(0, len(df) - 1, points), np.geomspace(1, len(df), points) - 1, best].astype(int))
    return pd.DataFrame({"dihubungi": idx + 1, "pendapatan_kotor": gross[idx], "biaya": spend[idx], "profit_bersih": profit[idx],
                         "konversi": np.cumsum(y)[idx], "terbaik": idx == best})


def curve(engine: str, steps: int = 40, **kw) -> pd.DataFrame:
    df = pd.read_parquet(path("processed") / "scores" / f"{engine}_test.parquet", columns=["label"])
    ns = np.unique(np.linspace(1, len(df), steps).astype(int))
    rows = []
    for n in ns:
        for name, sc in [("Model (nilai harapan)", "nilai_harapan"), ("Model (peluang)", "skor"), ("Baseline bisnis", "skor_baseline")]:
            rows.append({"dihubungi": int(n), "versi": name, **evaluate(engine, int(n), sc, **kw)})
    return pd.DataFrame(rows)


def mis_selling_prevented(p: dict | None = None) -> dict:
    """Recommendations the output guardrail blocked (audit log) x mis-selling cost."""
    from src.guardrails import audit_log
    import json
    p = p or assumptions()
    log = audit_log.read(5000)
    blocked = sum(len(json.loads(g).get("diblokir", [])) for g in log["guardrail_output"].fillna("{}")) if len(log) else 0
    return {"kasus_diblokir": blocked, "rugi_dicegah": blocked * p["biaya_salah_jual"]}
