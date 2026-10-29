"""Bank product holdings: a month-1 snapshot and monthly movement for the whole calendar.

Levels (share of customers holding a product) come from Indonesian sources where they
exist (AKKI, OJK SNLIK, LPS, Bank mobile banking users) and from Santander otherwise; every level
is reported with its source in output/produk_level.csv. The *shape* (how holding moves
with age band and income rank, which products go together, monthly churn) comes from
the real Santander panel (calibrate/dinamika_santander.py).
"""
import re

import numpy as np
import pandas as pd
from scipy.stats import norm

from .people import age_band
from .ref import Ref

QUINTILES = ["Q1", "Q2", "Q3", "Q4", "Q5"]


def slug(name: str) -> str:
    return "prod_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def primary_product(age: np.ndarray, occupation: np.ndarray, cfg: dict) -> np.ndarray:
    """Catalog rules: under 17 -> Tabungan Plus Anak; students, first jobbers and young people
    17-35 -> Tabungan Plus Muda; everyone else -> Tabungan Plus."""
    young = (age >= 17) & (age <= 35) & ((occupation == "Pelajar/Mahasiswa") | (age <= cfg["umur_maks_first_jobber"]))
    return np.where(age < 17, "Tabungan Plus Anak", np.where(young, "Tabungan Plus Muda", "Tabungan Plus"))


def additional_products(ref: Ref) -> pd.DataFrame:
    return ref.product_model[ref.product_model["jenis"] == "tambahan"].reset_index(drop=True)


def product_levels(ref: Ref) -> pd.DataFrame:
    """Target share of Bank customers holding each additional product, with its source."""
    pm = additional_products(ref)
    dyn = ref.dyn_products.set_index("kolom_santander")["level"]
    sector = ref.snlik("inklusi", "sektor")
    banked_adults = sector["Perbankan"] / 100 * ref.indicator("penduduk_15_79")
    rows = []
    for r in pm.itertuples():
        how, own = r.cara_level, dyn[r.analog_santander]
        group_share = own / dyn[pm.loc[pm["cara_level"] == how, "analog_santander"]].sum()
        if how == "akki":
            level = ref.indicator("kartu_kredit_beredar") / ref.cfg["produk"]["kartu_per_pemegang"] / banked_adults
            src = "AKKI kartu beredar Jun 2025 / (SNLIK inklusi perbankan x penduduk 15-79); ASUMSI 1 kartu per pemegang"
        elif how == "mobile banking":
            level = ref.indicator("pengguna_mobile") / (ref.cfg["produk"]["nasabah_bank_juta"] * 1e6)
            src = "Pengguna mobile banking H1 2026 / jumlah nasabah Bank (ASUMSI, config)"
        elif how.startswith("snlik:"):
            level = sector[how.split(":")[1]] / sector["Perbankan"]
            src = f"SNLIK 2025 inklusi sektor {how.split(':')[1]} / perbankan"
        elif how.startswith("snlik_bagi:"):
            level = sector[how.split(":")[1]] / sector["Perbankan"] * group_share
            src = f"SNLIK 2025 inklusi sektor {how.split(':')[1]} / perbankan, dibagi antar produk menurut rasio Santander"
        elif how == "lps_nontabungan":
            per_person = ref.indicator("rekening_simpanan_bank_umum") / banked_adults
            level = (1 - ref.indicator("porsi_rekening_tabungan")) * per_person * group_share
            src = "LPS Apr 2026 rekening non-tabungan per orang ber-rekening, dibagi menurut rasio Santander (termasuk rekening badan usaha: batas atas)"
        elif how == "santander":
            level, src = own, f"Santander {r.analog_santander} (tidak ada data publik Indonesia)"
        elif how == "santander_top":
            level, src = ref.extra("porsi_segmen_top"), "Santander porsi segmen 01-TOP (tidak ada data publik Indonesia)"
        else:
            raise ValueError(f"cara_level tidak dikenal: {how}")
        rows.append({"produk": r.produk, "kolom": slug(r.produk), "level_target": level, "sumber_level": src,
                     "analog_santander": r.analog_santander})
    return pd.DataFrame(rows)


def eligibility(pm: pd.DataFrame, age: np.ndarray, occupation: np.ndarray, income: np.ndarray) -> np.ndarray:
    """Catalog and regulator rules per product (reference/produk_model.csv)."""
    out = np.zeros((len(age), len(pm)), dtype=bool)
    for j, r in enumerate(pm.itertuples()):
        ok = (age >= int(r.umur_min)) & (age <= int(r.umur_max)) & (income >= float(r.pendapatan_min))
        if r.pekerjaan_syarat != "semua":
            ok &= np.isin(occupation, r.pekerjaan_syarat.split(";"))
        out[:, j] = ok
    return out


def income_quintile(cust: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """Income rank inside the province (ties broken randomly), as in the calibration."""
    noise = rng.random(len(cust))
    rank = pd.DataFrame({"p": cust["provinsi"], "y": cust["pendapatan_bulanan_idr"] + noise})
    pct = rank.groupby("p")["y"].rank(pct=True).to_numpy()
    return np.array(QUINTILES)[np.minimum((pct * 5).astype(int), 4)]


class Propensity:
    """p[i, j] = scale_j x age_j(i) x income_j(i), zero where the catalog says the customer
    is not eligible. scale_j is fitted once (month 1) so the mean over customers equals the
    level target, then kept fixed as people age. The age and income factors are, per product:
    - capital-market products (cara_level snlik_bagi:Pasar Modal): factors raked so holders
      follow the KSEI Oct 2025 investor mix by age and annual income (Indonesian source);
    - products in config produk.gradien_pendapatan: Santander age ratio x (income / median
      earner income) ^ beta (ASUMSI: no Indonesian per-income data for these products);
    - all others: Santander age ratio x Santander income-quintile ratio."""

    def __init__(self, ref: Ref, levels: pd.DataFrame):
        self.pm = additional_products(ref)
        self.cap = ref.cfg["produk"]["peluang_maks"]
        self.rr_age = ref.rr_age.set_index("kolom_santander")
        self.rr_inc = ref.rr_income.set_index("kolom_santander")
        self.levels = levels.set_index("produk")["level_target"]
        self.beta = ref.cfg["produk"].get("gradien_pendapatan", {})
        self.ksei = ref.ksei
        self.capital = self.pm["cara_level"].str.endswith("Pasar Modal").to_numpy()
        self.scale = self.ksei_age = self.ksei_inc = self.median = None

    def ksei_bands(self, age, income):
        k = self.ksei
        a, y = k[k["dimensi"] == "umur"], k[k["dimensi"] == "penghasilan_tahunan"]
        ab = np.searchsorted(a["batas_atas"].to_numpy(), age, side="right")
        yb = np.searchsorted(y["batas_atas"].to_numpy(), income * 12, side="right")
        return ab, yb, a["porsi_investor"].to_numpy(), y["porsi_investor"].to_numpy()

    def raw(self, age, occupation, quintile, income):
        band = age_band(age).to_numpy()
        out = np.zeros((len(age), len(self.pm)))
        ab, yb, _, _ = self.ksei_bands(age, income)
        for j, r in enumerate(self.pm.itertuples()):
            if self.capital[j] and self.ksei_age is not None:
                out[:, j] = self.ksei_age[ab] * self.ksei_inc[yb]
                continue
            a = self.rr_age.loc[r.analog_santander].reindex(band).fillna(1.0).to_numpy()
            if r.produk in self.beta:
                q = (np.maximum(income, 500_000) / self.median) ** float(self.beta[r.produk])
            else:
                q = self.rr_inc.loc[r.analog_santander].reindex(quintile).fillna(1.0).to_numpy()
            out[:, j] = np.maximum(a * q, 0.01)  # floor: Santander zero cells are small-sample
        return out * eligibility(self.pm, age, occupation, income)

    def fit(self, age, occupation, quintile, income):
        earners = income > 0
        self.median = float(np.median(income[earners])) if earners.any() else 1.0
        self.fit_ksei(age, occupation, income)
        raw = self.raw(age, occupation, quintile, income)
        self.scale = np.ones(raw.shape[1])
        for j in range(raw.shape[1]):
            target = self.levels[self.pm.loc[j, "produk"]] * len(age)
            for _ in range(30):  # re-scale until the capped probabilities hit the target
                got = np.minimum(raw[:, j] * self.scale[j], self.cap).sum()
                self.scale[j] *= target / max(got, 1e-9)
        return self(age, occupation, quintile, income)

    def fit_ksei(self, age, occupation, income):
        """Rake one age factor and one income factor so expected holders match the KSEI
        investor shares on both margins (eligibility is the same for both products)."""
        ab, yb, ta, ty = self.ksei_bands(age, income)
        j = int(np.argmax(self.capital))
        ok = eligibility(self.pm.iloc[[j]].reset_index(drop=True), age, occupation, income)[:, 0]
        fa, fy = np.ones(len(ta)), np.ones(len(ty))
        for _ in range(100):
            w = fa[ab] * fy[yb] * ok
            fa *= ta / np.maximum(np.bincount(ab, w, len(ta)) / w.sum(), 1e-12)
            w = fa[ab] * fy[yb] * ok
            fy *= ty / np.maximum(np.bincount(yb, w, len(ty)) / w.sum(), 1e-12)
        self.ksei_age, self.ksei_inc = fa / fa.mean(), fy / fy.mean()

    def __call__(self, age, occupation, quintile, income):
        return np.minimum(self.raw(age, occupation, quintile, income) * self.scale, self.cap)


def latent_correlation(ref: Ref, analogs: list[str]) -> np.ndarray:
    c = ref.corr.loc[analogs, analogs].to_numpy().copy()
    same = np.equal.outer(np.array(analogs), np.array(analogs))
    c[same & ~np.eye(len(analogs), dtype=bool)] = 0.5  # ASUMSI: two products sharing one analog
    w, v = np.linalg.eigh(c)
    c = v @ np.diag(np.clip(w, 1e-4, None)) @ v.T     # nearest positive definite
    d = np.sqrt(np.diag(c))
    return c / d[:, None] / d[None, :]


def initial_holdings(p: np.ndarray, corr: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Gaussian copula: correlated latent draws keep Santander's co-ownership pattern."""
    z = rng.multivariate_normal(np.zeros(len(corr)), corr, size=p.shape[0], method="cholesky")
    return z < norm.ppf(np.clip(p, 1e-9, 1 - 1e-9))


def monthly_rates(ref: Ref, pm: pd.DataFrame) -> np.ndarray:
    return ref.dyn_products.set_index("kolom_santander").loc[pm["analog_santander"], "churn_bulanan"].to_numpy()


def step(hold: np.ndarray, p: np.ndarray, churn: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """One month. Holders leave with the Santander churn rate; non-holders join with
    churn x p/(1-p), so each person's long-run holding probability stays p."""
    hazard = np.minimum(churn * p / np.maximum(1 - p, 1e-6), 0.5)
    u = rng.random(hold.shape)
    return np.where(hold, u >= churn, (u < hazard) & (p > 0))
