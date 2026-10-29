"""Value chain around Bank corporate customers (anchors): companies, who works for or
owns them, and the money that flows between them each month.

Sourced: sector weights (BPS Aug 2025 workers by industry), turnover bands (PP 7/2021),
headcount bands (BPS), province weights (BPS 2026), Idul Fitri months (SKB 3 Menteri),
THR rule (Permenaker 6/2016), company products (Bank catalog). Everything else is an
assumption in config.yaml (value_chain).
"""
import numpy as np
import pandas as pd

from .people import banking_propensity, sample_population
from .ref import Ref

SCALES = ["Mikro", "Kecil", "Menengah", "Besar"]
OTHER_BANKS = ["BANK_A", "BANK_B", "BANK_C"]


def build_companies(ref: Ref, rng: np.random.Generator) -> pd.DataFrame:
    cfg, T = ref.cfg["value_chain"], ref.cfg["bulan"]
    n_a, n_c = cfg["jumlah_anchor"], cfg["jumlah_perusahaan"]
    n = n_a + n_c

    sec = ref.sectors[~ref.sectors["kode_kbli"].isin(cfg["sektor_dikecualikan"])]
    prov = ref.pop_prov
    df = pd.DataFrame({
        "company_id": [f"C{i:06d}" for i in range(n)],
        "is_anchor": np.r_[np.ones(n_a, bool), np.zeros(n_c, bool)],
        "sektor": rng.choice(sec["kode_kbli"], size=n, p=(sec["jumlah_pekerja"] / sec["jumlah_pekerja"].sum()).to_numpy()),
        "provinsi": rng.choice(prov["provinsi"], size=n, p=(prov["populasi_ribu"] / prov["populasi_ribu"].sum()).to_numpy()),
    })
    scale_a, scale_m = cfg["skala_anchor"], cfg["skala_mitra"]
    df["skala"] = np.r_[rng.choice(list(scale_a), n_a, p=list(scale_a.values())),
                        rng.choice(list(scale_m), n_c, p=list(scale_m.values()))]
    df["peran"] = np.r_[np.full(n_a, "ANCHOR"),
                        rng.choice(list(cfg["porsi_peran"]), n_c, p=list(cfg["porsi_peran"].values()))]
    df["nama_samaran"] = [
        f"PT Anchor {i:04d}" if a else (f"PT Mitra {i:04d}" if s in ("Menengah", "Besar") else f"CV Mitra {i:04d}")
        for i, (a, s) in enumerate(zip(df["is_anchor"], df["skala"]))
    ]

    # Turnover bands: PP 7/2021. Log-uniform inside each band (ASUMSI shape).
    lo = {"Mikro": cfg["omzet_min_mikro"], "Kecil": ref.indicator("omzet_maks_mikro"),
          "Menengah": ref.indicator("omzet_maks_kecil"), "Besar": ref.indicator("omzet_maks_menengah")}
    hi = {"Mikro": ref.indicator("omzet_maks_mikro"), "Kecil": ref.indicator("omzet_maks_kecil"),
          "Menengah": ref.indicator("omzet_maks_menengah"), "Besar": cfg["omzet_maks_besar"]}
    u = rng.random(n)
    df["omzet_tahunan_rp"] = np.round(np.exp(np.log(df["skala"].map(lo)) + u * np.log(df["skala"].map(hi) / df["skala"].map(lo))), -6)

    # Headcount bands: BPS (1-4, 5-19, 20-99, 100+); large firms follow a Pareto tail (ASUMSI).
    head = {"Mikro": (1, 4), "Kecil": (5, 19), "Menengah": (20, 99)}
    df["jumlah_karyawan"] = [
        rng.integers(*head[s], endpoint=True) if s in head
        else int(min(100 * (1 - rng.random()) ** (-1 / cfg["karyawan_besar_pareto_alpha"]), cfg["karyawan_besar_maks"]))
        for s in df["skala"]
    ]
    df["tahun_berdiri"] = rng.integers(*cfg["tahun_berdiri"], size=n, endpoint=True)

    is_bank = df["is_anchor"] | (rng.random(n) < cfg["porsi_perusahaan_bank"])
    df["bank_utama"] = np.where(is_bank, "Bank", rng.choice(OTHER_BANKS, n))
    df["bank_payroll"] = np.where(is_bank & (rng.random(n) < cfg["peluang_payroll_bank_jika_bank"]),
                                  "Bank", np.where(is_bank, rng.choice(OTHER_BANKS, n), df["bank_utama"]))
    df["is_bank_customer"] = is_bank.astype(np.int8)
    df["produk_bank"] = [company_products(r) for r in df.itertuples()]
    return df


def company_products(r) -> str:
    """Catalog names: Tabungan Plus Bisnis for unincorporated micro/small firms, Giro (Non
    Perorangan) + CIB for larger ones, CIB Supply Chain for anchors,
    Payroll Korporasi when salaries run through Bank."""
    if r.bank_utama != "Bank":
        return ""
    items = ["Tabungan Plus Bisnis"] if r.skala in ("Mikro", "Kecil") else ["Bank Giro (Non Perorangan)", "CIB"]
    if r.is_anchor:
        items.append("CIB Supply Chain")
    if r.bank_payroll == "Bank":
        items.append("Payroll Korporasi")
    return ";".join(items)


def build_relations(ref: Ref, comp: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Company-to-company links. Anchors attract partners in proportion to a Pareto
    weight, which gives the long-tailed degree distribution the guideline asks for."""
    cfg, T = ref.cfg["value_chain"], ref.cfg["bulan"]
    anchors = comp.index[comp["is_anchor"]].to_numpy()
    w = (1 - rng.random(len(anchors))) ** (-1 / cfg["pareto_daya_tarik_anchor"])
    w /= w.sum()
    rows = []
    partners = comp.index[~comp["is_anchor"]]
    for i in partners:
        role = comp.at[i, "peran"]
        for a in rng.choice(anchors, size=1 + rng.poisson(cfg["anchor_tambahan_rata2"]), replace=False, p=w):
            payer, payee = (i, a) if role == "DISTRIBUTOR" else (a, i)
            rows.append((payer, payee, role))
        # Partners sit in the anchor's province more often than not (ASUMSI).
        if rng.random() < cfg["peluang_mitra_satu_provinsi"]:
            comp.at[i, "provinsi"] = comp.at[rows[-1][0] if role != "DISTRIBUTOR" else rows[-1][1], "provinsi"]

    # Sub-suppliers: suppliers buy from smaller suppliers, so prospects exist two steps out.
    suppliers = comp.index[comp["peran"] == "SUPPLIER"].to_numpy()
    small = comp.index[(comp["peran"] == "SUPPLIER") & comp["skala"].isin(["Mikro", "Kecil"])].to_numpy()
    for s in suppliers:
        for t in rng.choice(small, size=min(rng.poisson(cfg["sub_supplier_rata2"]), len(small)), replace=False):
            if t != s:
                rows.append((s, t, "SUPPLIER"))

    rel = pd.DataFrame(rows, columns=["payer", "payee", "jenis_relasi_asli"]).drop_duplicates(["payer", "payee"])
    n = len(rel)
    rel["bulan_mulai"] = np.where(rng.random(n) < cfg["porsi_relasi_mulai_sebelum_panel"], 1, rng.integers(2, T + 1, n))
    life = rng.geometric(cfg["laju_putus_relasi_bulanan"], n)
    rel["bulan_selesai"] = np.minimum(rel["bulan_mulai"] + life - 1, T)
    rel["porsi_omzet"] = rng.uniform(*cfg["porsi_omzet_ke_mitra"], n)
    rel["jenis_relasi_terlihat"] = np.where(rng.random(n) < cfg["porsi_relasi_tidak_diketahui"], "UNKNOWN", rel["jenis_relasi_asli"])
    rel["from_id"] = comp.loc[rel["payer"], "company_id"].to_numpy()
    rel["to_id"] = comp.loc[rel["payee"], "company_id"].to_numpy()
    return rel.reset_index(drop=True)


def build_people(ref: Ref, comp: pd.DataFrame, pop: pd.DataFrame, customers: pd.DataFrame,
                 panel: pd.DataFrame, rng: np.random.Generator):
    """Employees and owners. A customer who ever holds Bank Payroll works for a company
    that pays salaries through Bank. Prospects work for those same companies but are
    paid into accounts at other banks: the salary leaves a Bank account, so the bank
    really can see them (name, receiving bank, amount), which is what makes them
    reachable prospects in real life."""
    cfg = ref.cfg["value_chain"]
    cap = np.minimum(comp["jumlah_karyawan"].to_numpy(), cfg["karyawan_dimaterialisasi_maks"])
    bank_payroll = comp["bank_payroll"].to_numpy() == "Bank"

    payroll_ids = panel.loc[panel["prod_bank_payroll"] == 1, "person_id"].unique()
    in_panel = customers.set_index("person_id")
    others = in_panel.index[(in_panel["pekerjaan"] == "Pegawai/Profesional") & ~in_panel.index.isin(payroll_ids)]
    n_other = max(cfg["jumlah_nasabah_terhubung"] - len(payroll_ids), 0)
    linked_other = rng.choice(others, size=min(n_other, len(others)), replace=False)

    prospects = pop[(pop["pekerjaan"] == "Pegawai/Profesional") & ~pop["person_id"].isin(customers["person_id"])]
    need = cfg["jumlah_prospek_perorangan"]
    if len(prospects) < need:  # top up from a fresh population draw
        extra = sample_population(ref, (need - len(prospects)) * 8, rng)
        extra["punya_rekening_bank"] = (rng.random(len(extra)) < banking_propensity(ref, extra)).astype(np.int8)
        extra = extra[extra["pekerjaan"] == "Pegawai/Profesional"].copy()
        extra.insert(0, "person_id", [f"Q{i:07d}" for i in range(len(extra))])
        prospects = pd.concat([prospects, extra], ignore_index=True)
    prospects = prospects.sample(n=need, random_state=int(rng.integers(1 << 31)))

    def assign(person_ids, mask):
        slots = np.repeat(np.flatnonzero(mask), cap[mask])
        take = rng.choice(slots, size=len(person_ids), replace=len(person_ids) > len(slots))
        return pd.DataFrame({"person_id": person_ids, "company_idx": take})

    emp = pd.concat([assign(payroll_ids, bank_payroll),
                     assign(linked_other, ~bank_payroll),
                     assign(prospects["person_id"].to_numpy(), bank_payroll)], ignore_index=True)
    emp["peran"] = "KARYAWAN"

    # One owner per micro/small company, drawn from the self-employed population.
    owners_pool = pop[pop["pekerjaan"] == "Pengusaha/Wiraswasta"]
    small = np.flatnonzero(comp["skala"].isin(["Mikro", "Kecil"]).to_numpy())
    owners = owners_pool.sample(n=min(len(small), len(owners_pool)), random_state=int(rng.integers(1 << 31)))
    emp = pd.concat([emp, pd.DataFrame({"person_id": owners["person_id"].to_numpy(),
                                        "company_idx": small[:len(owners)], "peran": "PEMILIK"})], ignore_index=True)
    # Traders: self-employed people outside Bank who buy from Bank distributors and anchors, so
    # their payments land in a Bank account and the bank can see them (grill me Q12, Q19).
    taken = set(emp["person_id"]) | set(customers["person_id"])
    pool = pop[(pop["pekerjaan"] == "Pengusaha/Wiraswasta") & (pop["pendapatan_bulanan_idr"] > 0) & ~pop["person_id"].isin(taken)]
    traders = pool.sample(n=min(cfg["jumlah_pedagang"], len(pool)), random_state=int(rng.integers(1 << 31)))
    sellers = np.flatnonzero(((comp["is_bank_customer"] == 1) & comp["peran"].isin(["DISTRIBUTOR", "ANCHOR"])).to_numpy())
    w = np.sqrt(comp["omzet_tahunan_rp"].to_numpy()[sellers])
    emp = pd.concat([emp, pd.DataFrame({"person_id": traders["person_id"].to_numpy(), "peran": "PEMBELI",
                                        "company_idx": rng.choice(sellers, size=len(traders), p=w / w.sum())})], ignore_index=True)
    emp["company_id"] = comp.loc[emp["company_idx"], "company_id"].to_numpy()
    emp["bulan_mulai"], emp["bulan_selesai"] = 1, ref.cfg["bulan"]

    people_ids = pd.Index(emp["person_id"]).union(customers["person_id"])
    allpop = pd.concat([pop, prospects[~prospects["person_id"].isin(pop["person_id"])]], ignore_index=True)
    persons = allpop.set_index("person_id").loc[people_ids].reset_index()
    persons["is_bank_customer"] = persons["person_id"].isin(customers["person_id"]).astype(np.int8)
    # Salaried prospects need an account to be paid into, so they always bank somewhere.
    banked = (persons["punya_rekening_bank"].fillna(1).astype(int) == 1) | persons["person_id"].isin(prospects["person_id"]) \
        | persons["person_id"].isin(traders["person_id"])
    persons["bank_utama"] = np.where(persons["is_bank_customer"] == 1, "Bank",
                                     np.where(banked, rng.choice(OTHER_BANKS, len(persons)), "TIDAK ADA"))
    employer = emp[emp["peran"] == "KARYAWAN"].drop_duplicates("person_id").set_index("person_id")["company_idx"]
    persons["bank_payroll"] = persons["person_id"].map(employer).map(comp["bank_payroll"]).fillna("")
    persons = persons[["person_id", "usia", "jenis_kelamin", "provinsi", "perkotaan", "pekerjaan",
                       "pendapatan_bulanan_idr", "is_bank_customer", "bank_utama", "bank_payroll"]]
    return persons, emp.drop(columns="company_idx")


def build_transfers(ref: Ref, comp: pd.DataFrame, rel: pd.DataFrame, emp: pd.DataFrame,
                    persons: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    cfg, T = ref.cfg["value_chain"], ref.cfg["bulan"]
    thr = ref.calendar.set_index("bulan_ke")["bulan_thr"]
    lam = cfg["transaksi_per_bulan"]
    monthly_omzet = comp["omzet_tahunan_rp"].to_numpy() / 12
    lebaran = {k: v for k, v in cfg["efek_lebaran_sektor"].items()}
    out = []
    for t in range(1, T + 1):
        live = rel[(rel["bulan_mulai"] <= t) & (rel["bulan_selesai"] >= t)]
        base = np.minimum(monthly_omzet[live["payer"]], monthly_omzet[live["payee"]]) * live["porsi_omzet"].to_numpy()
        season = np.where(thr[t] == 1, comp.loc[live["payer"], "sektor"].map(lebaran).fillna(1.0).to_numpy(), 1.0)
        amount = np.round(base * season * np.exp(rng.normal(0, cfg["noise_nominal_sd_log"], len(live))), -3)
        count = rng.poisson(live["jenis_relasi_asli"].map(lam).to_numpy())
        keep = count > 0
        out.append(pd.DataFrame({"bulan_ke": t, "from_id": live["from_id"].to_numpy()[keep], "to_id": live["to_id"].to_numpy()[keep],
                                 "jenis_relasi_terlihat": live["jenis_relasi_terlihat"].to_numpy()[keep],
                                 "total_nominal_rp": amount[keep], "jumlah_transaksi": count[keep]}))

    # Payroll: monthly salary = the person's income; THR (1x) in the Idul Fitri month.
    pay = emp[emp["peran"] == "KARYAWAN"].merge(persons[["person_id", "pendapatan_bulanan_idr"]], on="person_id")
    pay = pay[pay["pendapatan_bulanan_idr"] > 0]
    for t in range(1, T + 1):
        mult = 1 + cfg["thr_kali_upah"] * thr[t]
        out.append(pd.DataFrame({"bulan_ke": t, "from_id": pay["company_id"].to_numpy(), "to_id": pay["person_id"].to_numpy(),
                                 "jenis_relasi_terlihat": "PAYROLL", "total_nominal_rp": pay["pendapatan_bulanan_idr"].to_numpy() * mult,
                                 "jumlah_transaksi": 1 + thr[t]}))
    # Traders pay their supplier for goods: income x a purchase multiple (ASUMSI), with the
    # same Lebaran lift as the seller's sector; part of the relation type is unknown to the bank.
    buy = emp[emp["peran"] == "PEMBELI"].merge(persons[["person_id", "pendapatan_bulanan_idr"]], on="person_id")
    mult = rng.uniform(*cfg["pembelian_pedagang_kali_penghasilan"], len(buy))
    seller_sector = buy["company_id"].map(comp.set_index("company_id")["sektor"])
    seen_type = np.where(rng.random(len(buy)) < cfg["porsi_relasi_tidak_diketahui"], "UNKNOWN", "PEMBELI")
    for t in range(1, T + 1):
        lift = np.where(thr[t] == 1, seller_sector.map(lebaran).fillna(1.0).to_numpy(), 1.0)
        amount = np.round(buy["pendapatan_bulanan_idr"].to_numpy() * mult * lift * np.exp(rng.normal(0, 0.3, len(buy))), -3)
        out.append(pd.DataFrame({"bulan_ke": t, "from_id": buy["person_id"].to_numpy(), "to_id": buy["company_id"].to_numpy(),
                                 "jenis_relasi_terlihat": seen_type, "total_nominal_rp": amount,
                                 "jumlah_transaksi": 1 + rng.poisson(cfg["transaksi_pedagang_per_bulan"] - 1, len(buy))}))
    tr = pd.concat(out, ignore_index=True)
    bulan = ref.calendar.set_index("bulan_ke")["bulan"]
    tr.insert(1, "bulan", tr["bulan_ke"].map(bulan))
    return tr


def relationship_truth(rel: pd.DataFrame, emp: pd.DataFrame) -> pd.DataFrame:
    a = rel[["from_id", "to_id", "jenis_relasi_asli", "bulan_mulai", "bulan_selesai"]]
    trader = emp["peran"] == "PEMBELI"
    b = emp.assign(from_id=np.where(trader, emp["person_id"], emp["company_id"]),
                   to_id=np.where(trader, emp["company_id"], emp["person_id"]),
                   jenis_relasi_asli=emp["peran"].map({"PEMILIK": "OWNER", "PEMBELI": "PEMBELI"}).fillna("PAYROLL"))
    return pd.concat([a, b[["from_id", "to_id", "jenis_relasi_asli", "bulan_mulai", "bulan_selesai"]]], ignore_index=True)
