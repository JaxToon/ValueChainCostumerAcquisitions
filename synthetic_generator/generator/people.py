"""Synthetic Indonesian adults (15-79) and the Bank customers drawn from them.

Sources (reference/SUMBER.md): BPS age x sex 2025, BPS province population 2026,
OJK SNLIK 2025 profile and inclusion, BPS wage distribution Aug 2025.
"""
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import norm

from .ref import AGE_BANDS, AGE_EDGES, EARNING, INCOME_BANDS, INCOME_EDGES, NO_INCOME, OCCUPATIONS, Ref


def age_band(age) -> pd.Series:
    return pd.cut(pd.Series(age), AGE_EDGES, right=False, labels=AGE_BANDS).astype(str)


def income_band(income) -> pd.Series:
    income = pd.Series(income)
    band = pd.cut(income, INCOME_EDGES, right=False, labels=INCOME_BANDS).astype(str)
    return band.where(income > 0, NO_INCOME)


def single_age_weights(ref: Ref) -> pd.DataFrame:
    """Weights per single age x sex for 15-79. BPS 5-year groups are spread evenly over
    their ages, then each SNLIK age band is rescaled to its SNLIK 15-79 total."""
    share_75 = ref.cfg["nasabah"]["porsi_75_79_dari_75plus"]
    rows = []
    for _, r in ref.pop_age_sex.iterrows():
        label = str(r["kelompok_umur"]).strip()
        if label.endswith("+"):
            lo, hi, share = int(label[:-1]), 79, share_75
        else:
            lo, hi = (int(x) for x in label.split("-"))
            share = 1.0
        span = hi - lo + 1
        for a in range(max(lo, 15), min(hi, 79) + 1):
            rows.append((a, r["laki_laki_ribu"] * share / span, r["perempuan_ribu"] * share / span))
    w = pd.DataFrame(rows, columns=["usia", "Laki-Laki", "Perempuan"])
    band = age_band(w["usia"])
    target = ref.snlik("profil", "umur")
    factor = band.map(target / (w["Laki-Laki"] + w["Perempuan"]).groupby(band).sum())
    w[["Laki-Laki", "Perempuan"]] = w[["Laki-Laki", "Perempuan"]].mul(factor, axis=0)
    return w


def occupation_eligible(age: np.ndarray, cfg: dict) -> np.ndarray:
    """1 where an occupation is possible at that age. ASUMSI (config): students up to the
    student age limit, retirees from the retiree age limit."""
    ok = np.ones((len(age), len(OCCUPATIONS)))
    ok[age > cfg["umur_maks_pelajar"], OCCUPATIONS.index("Pelajar/Mahasiswa")] = 0
    ok[age < cfg["umur_min_pensiunan"], OCCUPATIONS.index("Pensiunan/Purnawirawan")] = 0
    return ok


def occupation_given_band(ref: Ref, w: pd.DataFrame):
    """P(occupation | age band) by iterative proportional fitting to the SNLIK age and
    occupation totals. The seed is the share of each band's population for whom the
    occupation is possible, so the single-age limits are part of the fit, not applied after."""
    cfg = ref.cfg["nasabah"]
    occ = ref.snlik("profil", "pekerjaan")[OCCUPATIONS].to_numpy()
    ages = ref.snlik("profil", "umur")[AGE_BANDS].to_numpy()
    weight = (w["Laki-Laki"] + w["Perempuan"]).to_numpy()
    band = age_band(w["usia"]).to_numpy()
    ok = occupation_eligible(w["usia"].to_numpy(), cfg)
    seed = np.array([(ok[band == b] * weight[band == b, None]).sum(axis=0) / weight[band == b].sum() for b in AGE_BANDS])
    m = seed.copy()
    for _ in range(500):
        m *= (ages / m.sum(axis=1))[:, None]
        m *= occ / m.sum(axis=0)
    p = m / m.sum(axis=1, keepdims=True)
    # Per-age probability = band probability spread over the ages where it is possible.
    return pd.DataFrame(p / np.where(seed > 0, seed, 1), index=AGE_BANDS, columns=OCCUPATIONS)


def sample_population(ref: Ref, n: int, rng: np.random.Generator) -> pd.DataFrame:
    cfg = ref.cfg["nasabah"]
    w = single_age_weights(ref).melt(id_vars="usia", var_name="jenis_kelamin", value_name="w")
    pick = rng.choice(len(w), size=n, p=(w["w"] / w["w"].sum()).to_numpy())
    pop = w.iloc[pick][["usia", "jenis_kelamin"]].reset_index(drop=True)
    pop["kelompok_umur"] = age_band(pop["usia"]).to_numpy()

    # ASUMSI: every province has the national age-sex structure (BPS 2026 gives totals only).
    prov = ref.pop_prov
    pop["provinsi"] = rng.choice(prov["provinsi"], size=n, p=(prov["populasi_ribu"] / prov["populasi_ribu"].sum()).to_numpy())
    # ASUMSI: urban share is national (SNLIK) in every province.
    desa = ref.snlik("profil", "desa")
    pop["perkotaan"] = (rng.random(n) < desa["Perkotaan"] / desa.sum()).astype(np.int8)

    pop["pekerjaan"] = sample_occupation(ref, pop, rng)
    pop["pendapatan_bulanan_idr"] = sample_income(ref, pop, rng)
    return pop


def sample_occupation(ref: Ref, pop: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    cfg = ref.cfg["nasabah"]
    base = occupation_given_band(ref, single_age_weights(ref))
    female_share = (pop["jenis_kelamin"] == "Perempuan").groupby(pop["kelompok_umur"]).mean()
    irt = OCCUPATIONS.index("Ibu Rumah Tangga")
    out = np.empty(len(pop), dtype=object)
    for (band, sex), idx in pop.groupby(["kelompok_umur", "jenis_kelamin"]).groups.items():
        idx = np.asarray(idx)
        p = base.loc[band].to_numpy()[None, :] * occupation_eligible(pop["usia"].to_numpy()[idx], cfg)
        p /= p.sum(axis=1, keepdims=True)
        # Ibu Rumah Tangga is female by definition: women get the band's whole IRT share
        # (t / female share), the other occupations keep their proportions in both sexes,
        # so every occupation's total is unchanged.
        t = p[:, irt].copy()
        others = p.copy()
        others[:, irt] = 0
        others /= others.sum(axis=1, keepdims=True)
        q = np.minimum(t / female_share[band], 0.95) if sex == "Perempuan" else np.zeros_like(t)
        p = others * (1 - q)[:, None]
        p[:, irt] = q
        draw = (rng.random(len(idx))[:, None] > p.cumsum(axis=1)).sum(axis=1)
        out[idx] = np.array(OCCUPATIONS, dtype=object)[np.minimum(draw, len(OCCUPATIONS) - 1)]
    return out


def other_earner_band_shares(ref: Ref) -> pd.Series:
    """Income bands for earners who are not employees. SNLIK gives bands for all 136.8 m
    earners; BPS gives the wage distribution of employees. Remove the employees' expected
    band counts (BPS national log-normal x SNLIK employee count) and keep the remainder."""
    nat = ref.wage_lognormal.set_index(["provinsi", "jenis_kelamin"]).loc[("INDONESIA", "Total")]
    edges = np.log(np.array(INCOME_EDGES[1:-1]))
    cdf = np.r_[0, norm.cdf((edges - nat["mu"]) / nat["sigma"]), 1]
    employees = ref.snlik("profil", "pekerjaan")["Pegawai/Profesional"] * np.diff(cdf)
    total = ref.snlik("profil", "pendapatan")[INCOME_BANDS].to_numpy()
    rest = np.clip(total - employees, 0, None)
    return pd.Series(rest / rest.sum(), index=INCOME_BANDS)


def wage_age_factor(ref: Ref, employees: pd.DataFrame) -> np.ndarray:
    """Multiplier giving employees the BPS Aug 2025 wage-by-age profile of their sex
    (Tabel 4.41/4.44/4.45: mean wage per age group / mean wage of all ages). Rescaled to
    mean 1 inside each province x sex, so the BPS provincial means still hold."""
    w = ref.wage_age[ref.wage_age["kelompok_umur"] != "Rata-rata"]
    avg = ref.wage_age.set_index("kelompok_umur").loc["Rata-rata"]
    edges = [*w["umur_min"], 80]
    band = pd.cut(employees["usia"], edges, right=False, labels=w["kelompok_umur"]).astype(str)
    sex = employees["jenis_kelamin"].map({"Laki-Laki": "Pria", "Perempuan": "Perempuan"})
    ratio = {s: (w[s] / avg[s]).set_axis(w["kelompok_umur"]) for s in ["Pria", "Perempuan"]}
    f = pd.Series([ratio[s_][b] for s_, b in zip(sex, band)], index=employees.index)
    return (f / f.groupby([employees["provinsi"], sex]).transform("mean")).to_numpy()


def sample_income(ref: Ref, pop: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """Employees draw from the BPS Aug 2025 wage log-normal of their province and sex,
    shaped by the BPS wage-by-age profile (wage_age_factor).
    Other earners draw an SNLIK income band (other_earner_band_shares), log-uniform inside
    it (top band: BPS national tail above Rp3.5 m), scaled by their province's BPS mean
    wage relative to the national mean (ASUMSI). Students, housewives and the never
    employed have no own income: SNLIK's 36.0% "no economic activity" equals those groups."""
    params = ref.wage_lognormal.set_index(["provinsi", "jenis_kelamin"])
    n = len(pop)
    income = np.zeros(n)

    emp = (pop["pekerjaan"] == "Pegawai/Profesional").to_numpy()
    sex_key = pop["jenis_kelamin"].map({"Laki-Laki": "Pria", "Perempuan": "Perempuan"})
    keys = pd.MultiIndex.from_arrays([pop["provinsi"], sex_key])
    mu, sd = params["mu"].reindex(keys).to_numpy(), params["sigma"].reindex(keys).to_numpy()
    income[emp] = np.exp(mu[emp] + sd[emp] * rng.standard_normal(emp.sum()))
    income[emp] *= wage_age_factor(ref, pop[emp])

    other = (pop["pekerjaan"].isin(EARNING).to_numpy()) & ~emp
    band = rng.choice(len(INCOME_BANDS), size=other.sum(), p=other_earner_band_shares(ref).to_numpy())
    lo = np.array([50_000, *INCOME_EDGES[1:-1]])[band]          # ASUMSI: floor Rp50 rb
    hi = np.array(INCOME_EDGES[1:], dtype=float)[band]
    x = np.exp(np.log(lo) + rng.random(len(band)) * np.log(np.where(np.isinf(hi), lo * 2, hi) / lo))
    nat = params.loc[("INDONESIA", "Total")]
    top = np.isinf(hi)
    u = norm.cdf((np.log(INCOME_EDGES[-2]) - nat["mu"]) / nat["sigma"])
    x[top] = np.exp(nat["mu"] + nat["sigma"] * norm.ppf(u + (1 - u) * rng.random(top.sum()) * 0.999))
    prov_ratio = (params.xs("Total", level="jenis_kelamin")["rata_rata_bps_rp"] / nat["rata_rata_bps_rp"])
    income[other] = x * pop.loc[other, "provinsi"].map(prov_ratio).to_numpy()
    return np.round(income, -3)


def banking_propensity(ref: Ref, pop: pd.DataFrame) -> np.ndarray:
    """P(has a bank account | person) as an additive logit over SNLIK characteristics,
    raked so each characteristic's inclusion matches SNLIK 2025. SNLIK publishes these
    for all sectors combined; ASUMSI: banking inclusion moves proportionally
    (scaled by banking 70.65% / all-sector 80.51%)."""
    scale = ref.snlik("inklusi", "sektor")["Perbankan"] / ref.snlik("inklusi", "nasional")["Indonesia"]
    dims = {
        "umur": pop["kelompok_umur"],
        "desa": pop["perkotaan"].map({1: "Perkotaan", 0: "Perdesaan"}),
        "gender": pop["jenis_kelamin"],
        "pekerjaan": pop["pekerjaan"],
        "pendapatan": income_band(pop["pendapatan_bulanan_idr"]),
    }
    targets = {d: (ref.snlik("inklusi", d) / 100 * scale).clip(0.01, 0.99) for d in dims}
    eta = np.full(len(pop), logit(ref.snlik("inklusi", "sektor")["Perbankan"] / 100))
    for _ in range(200):
        for d, cat in dims.items():
            p = expit(eta)
            current = pd.Series(p).groupby(cat.to_numpy()).mean()
            adj = (logit(targets[d].reindex(current.index)) - logit(current.clip(1e-4, 1 - 1e-4))).fillna(0)
            eta += cat.map(adj).to_numpy()
    return expit(eta)


def tenure_months(ref: Ref, ages: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Months as customer at month 1: Santander tenure quantiles (real bank data; no
    Indonesian source), capped so nobody became a customer before age 15."""
    q = ref.santander_extra[ref.santander_extra["indikator"].str.startswith("lama_nasabah_bulan_p")]
    levels = q["indikator"].str.extract(r"p(\d+)")[0].astype(float).to_numpy() / 100
    t = np.interp(rng.random(len(ages)), levels, q["nilai"].to_numpy())
    return np.minimum(np.round(t), np.maximum((ages - 15) * 12, 0)).astype(int)
