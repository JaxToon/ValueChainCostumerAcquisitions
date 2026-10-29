"""Bank customers over 17 months: who they are, which products they hold each month,
and who joins or leaves along the way."""
import numpy as np
import pandas as pd

from . import products as P
from .people import banking_propensity, sample_population, tenure_months
from .ref import Ref

PRIMARY = ["Tabungan Plus", "Tabungan Plus Muda", "Tabungan Plus Anak"]
TRANSACTIONAL = ["Mobile Banking", "Bank Payroll", "Bank Visa Platinum", "Autodebit"]


def build(ref: Ref, rng: np.random.Generator):
    cfg, T = ref.cfg["nasabah"], ref.cfg["bulan"]
    n0 = cfg["jumlah_awal"]

    pop = sample_population(ref, n0 * cfg["sampel_populasi_kali"], rng)
    pop.insert(0, "person_id", [f"P{i:07d}" for i in range(len(pop))])
    pop["peluang_rekening_bank"] = banking_propensity(ref, pop)
    pop["punya_rekening_bank"] = (rng.random(len(pop)) < pop["peluang_rekening_bank"]).astype(np.int8)
    pop["umur_desimal"] = pop["usia"] + rng.random(len(pop))      # ages move month by month
    pop["kuintil_pendapatan"] = P.income_quintile(pop, rng)

    banked = rng.permutation(np.flatnonzero(pop["punya_rekening_bank"].to_numpy()))
    members = list(banked[:n0])
    pool = list(banked[n0:])                                          # future new customers

    pm = P.additional_products(ref)
    levels = P.product_levels(ref)
    prop = P.Propensity(ref, levels)
    churn = P.monthly_rates(ref, pm)
    corr = P.latent_correlation(ref, pm["analog_santander"].tolist())
    exit_rate = ref.extra("laju_keluar_bulanan_median")
    entry_rate = ref.extra("laju_masuk_bulanan_median")
    mobile_idx = pm.index[pm["produk"] == "Mobile Banking"][0]
    payroll = pm.index[pm["produk"] == "Bank Payroll"][0]
    prioritas = pm.index[pm["produk"] == "Prioritas"][0]

    occ_all = pop["pekerjaan"].to_numpy()
    quint_all = pop["kuintil_pendapatan"].to_numpy()
    inc_all = pop["pendapatan_bulanan_idr"].to_numpy()

    def age_at(idx, t):
        return np.floor(pop["umur_desimal"].to_numpy()[idx] + (t - 1) / 12).astype(int)

    idx = np.array(members)
    p = prop.fit(age_at(idx, 1), occ_all[idx], quint_all[idx], inc_all[idx])
    hold = P.initial_holdings(p, corr, rng)
    joined = np.ones(len(idx), dtype=int)                           # month of joining (1 = before panel)

    static = pd.DataFrame({"pop_idx": idx, "bulan_masuk": 1})
    static["lama_nasabah_bulan_awal"] = tenure_months(ref, age_at(idx, 1), rng)
    static["channel"] = initial_channel(cfg, pop.iloc[idx], hold[:, payroll], rng)
    exits = {}
    frames = []
    for t in range(1, T + 1):
        if t > 1:
            leave = rng.random(len(idx)) < exit_rate
            for i in idx[leave]:
                exits[i] = t - 1                                    # last month present
            idx, hold, joined = idx[~leave], hold[~leave], joined[~leave]
            hold = P.step(hold, prop(age_at(idx, t), occ_all[idx], quint_all[idx], inc_all[idx]), churn, rng)

            k = min(rng.binomial(len(idx), entry_rate), len(pool))
            new, pool = np.array(pool[:k], dtype=int), pool[k:]
            new_hold = np.zeros((k, len(pm)), dtype=bool)
            # ASUMSI (config): a share of new customers open their account through mobile banking,
            # only if old enough for mobile banking under the product rules.
            allowed = P.eligibility(pm, age_at(new, t), occ_all[new], inc_all[new])[:, mobile_idx]
            new_hold[:, mobile_idx] = (rng.random(k) < cfg["nasabah_baru_mobile_peluang"]) & allowed
            idx, hold = np.concatenate([idx, new]), np.vstack([hold, new_hold])
            joined = np.concatenate([joined, np.full(k, t)])
            add = pd.DataFrame({"pop_idx": new, "bulan_masuk": t, "lama_nasabah_bulan_awal": 0})
            add["channel"] = np.where(new_hold[:, mobile_idx], "Mobile Banking",
                                      initial_channel(cfg, pop.iloc[new], new_hold[:, payroll], rng))
            static = pd.concat([static, add], ignore_index=True)

        age = age_at(idx, t)
        frame = pd.DataFrame({"person_id": pop["person_id"].to_numpy()[idx], "bulan_ke": t, "usia": age})
        primary = P.primary_product(age, occ_all[idx], cfg)
        for name in PRIMARY:
            frame[P.slug(name)] = (primary == name).astype(np.int8)
        for j, name in enumerate(pm["produk"]):
            frame[P.slug(name)] = hold[:, j].astype(np.int8)
        frame["aktif"] = frame[[P.slug(x) for x in TRANSACTIONAL]].max(axis=1).astype(np.int8)
        frame["segmen"] = np.where(hold[:, prioritas], "Prioritas",
                                   np.where(occ_all[idx] == "Pelajar/Mahasiswa", "Pelajar dan Mahasiswa", "Ritel"))
        frame["lama_nasabah_bulan"] = np.where(joined == 1, t - 1, t - joined)
        frames.append(frame)

    panel = pd.concat(frames, ignore_index=True)
    tenure0 = dict(zip(pop["person_id"].to_numpy()[static["pop_idx"]], static["lama_nasabah_bulan_awal"]))
    panel["lama_nasabah_bulan"] += panel["person_id"].map(tenure0)

    static["bulan_keluar"] = static["pop_idx"].map(exits)
    customers = pop.iloc[static["pop_idx"]].reset_index(drop=True)[
        ["person_id", "usia", "jenis_kelamin", "provinsi", "perkotaan", "pekerjaan", "pendapatan_bulanan_idr"]
    ].rename(columns={"usia": "usia_bulan1"})
    customers["bulan_masuk"] = static["bulan_masuk"].to_numpy()
    customers["bulan_keluar"] = static["bulan_keluar"].to_numpy()
    customers["lama_nasabah_bulan_saat_masuk_panel"] = static["lama_nasabah_bulan_awal"].to_numpy()
    customers["channel"] = static["channel"].to_numpy()
    return pop, customers, panel, levels


def initial_channel(cfg: dict, people: pd.DataFrame, has_payroll: np.ndarray, rng) -> np.ndarray:
    """Payroll customers come in through their employer; others through a branch, or in
    rural areas sometimes an Agen Bank agent (ASUMSI share, config)."""
    rural_agent = (people["perkotaan"].to_numpy() == 0) & (rng.random(len(people)) < cfg["peluang_agen_perdesaan"])
    return np.where(has_payroll, "Payroll Korporasi", np.where(rural_agent, "Agen Bank", "Kantor Cabang"))
