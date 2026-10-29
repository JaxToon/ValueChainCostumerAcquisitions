"""Compare the generated data with every reference it was built from and write
output/validation_report.md. Each section names its source; a check fails when the gap
is larger than the stated tolerance."""
import numpy as np
import pandas as pd

from .people import income_band
from .products import eligibility, slug
from .ref import Ref


class Report:
    def __init__(self):
        self.lines, self.fails = [], []

    def h(self, text):
        self.lines += ["", f"## {text}", ""]

    def p(self, text):
        self.lines.append(text)

    def table(self, df: pd.DataFrame):
        fmt = lambda v: f"{v:.4f}" if isinstance(v, (float, np.floating)) else str(v)
        self.lines.append("| " + " | ".join(map(str, df.columns)) + " |")
        self.lines.append("|" + " --- |" * len(df.columns))
        self.lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
        self.lines.append("")

    def info(self, name: str, detail: str):
        """Reported for comparison only; never fails the run (used for Santander, whose
        2015-2016 Spanish retail panel is a shape reference, not a target for Bank)."""
        self.lines.append(f"- INFO: {name} ({detail})")

    def check(self, name: str, ok: bool, detail: str):
        self.lines.append(f"- {'LOLOS' if ok else 'GAGAL'}: {name} ({detail})")
        if not ok:
            self.fails.append(name)


def compare(target: pd.Series, got: pd.Series, label: str) -> pd.DataFrame:
    df = pd.DataFrame({label: target.index, "target": target.to_numpy(),
                       "hasil": got.reindex(target.index).fillna(0).to_numpy()})
    df["selisih_poin_persen"] = (df["hasil"] - df["target"]) * 100
    return df


def run(ref: Ref, d: dict) -> Report:
    r = Report()
    r.p("# Laporan validasi data sintetis")
    r.p(f"Seed {ref.cfg['seed']}, {ref.cfg['bulan']} bulan. Toleransi: selisih proporsi <= 2 poin persen "
        "kecuali disebut lain. Sumber tiap rujukan: reference/SUMBER.md.")
    pop, cust, panel = d["population"], d["customers"], d["panel"]

    # 1. Population structure vs OJK SNLIK 2025 (15-79 years)
    r.h("1. Struktur penduduk 15-79 vs OJK SNLIK 2025")
    for dim, col, fn in [("umur", "kelompok_umur", None), ("gender", "jenis_kelamin", None),
                         ("pekerjaan", "pekerjaan", None), ("pendapatan", "pendapatan_bulanan_idr", income_band)]:
        target = ref.snlik("profil", dim)
        target = target / target.sum()
        values = fn(pop[col]) if fn else pop[col]
        t = compare(target, values.value_counts(normalize=True), dim)
        r.table(t)
        gap = t["selisih_poin_persen"].abs().max()
        r.check(f"sebaran {dim}", gap <= 2, f"selisih maks {gap:.2f} poin")
    urban = pop["perkotaan"].mean()
    target_urban = ref.snlik("profil", "desa")["Perkotaan"] / ref.snlik("profil", "desa").sum()
    r.check("porsi perkotaan", abs(urban - target_urban) * 100 <= 2, f"{urban:.3f} vs {target_urban:.3f}")

    # 2. Wages vs BPS Aug 2025 brackets (earners)
    r.h("2. Upah pegawai vs BPS Keadaan Pekerja Agustus 2025")
    r.p("BPS mengukur upah buruh/karyawan dan pekerja bebas, jadi yang dibandingkan adalah Pegawai/Profesional.")
    br = ref.wage_brackets.set_index(["provinsi", "jenis_kelamin"]).loc[("INDONESIA", "Total")]
    labels = ["lt_200rb", "200rb_399rb", "400rb_599rb", "600rb_799rb", "800rb_999rb", "1jt_1_49jt", "1_5jt_1_99jt", "2jt_plus"]
    target = pd.Series(br[labels].to_numpy(float) / float(br["jumlah"]), index=labels)
    earn = pop.loc[pop["pekerjaan"] == "Pegawai/Profesional", "pendapatan_bulanan_idr"]
    got = pd.cut(earn, [0, 2e5, 4e5, 6e5, 8e5, 1e6, 1.5e6, 2e6, np.inf], right=False, labels=labels).value_counts(normalize=True)
    t = compare(target, got, "kelompok_upah")
    r.table(t)
    gap = t["selisih_poin_persen"].abs().max()
    r.check("sebaran kelompok upah nasional", gap <= 12,
            f"selisih maks {gap:.2f} poin; toleransi 12 karena log-normal tidak menangkap ekor bawah pekerja informal")
    mean_bps = ref.wage_lognormal.set_index(["provinsi", "jenis_kelamin"])["rata_rata_bps_rp"]
    by_prov = pop[pop["pekerjaan"] == "Pegawai/Profesional"].groupby("provinsi")["pendapatan_bulanan_idr"].mean()
    ratio = (by_prov / mean_bps.xs("Total", level="jenis_kelamin").reindex(by_prov.index)).describe()
    r.check("rata-rata upah per provinsi", abs(ratio["50%"] - 1) <= 0.08,
            f"median rasio hasil/BPS {ratio['50%']:.3f}, rentang {ratio['min']:.2f}-{ratio['max']:.2f}")
    # Wage rises with age and drops after 55-59 (BPS Tabel 4.41/4.44/4.45): compare each
    # age group's mean relative to the all-age mean, per sex.
    wa = ref.wage_age[ref.wage_age["kelompok_umur"] != "Rata-rata"]
    avg = ref.wage_age.set_index("kelompok_umur").loc["Rata-rata"]
    emp = pop[pop["pekerjaan"] == "Pegawai/Profesional"]
    band = pd.cut(emp["usia"], [*wa["umur_min"], 80], right=False, labels=wa["kelompok_umur"])
    rows = []
    for sex, key in [("Laki-Laki", "Pria"), ("Perempuan", "Perempuan")]:
        m = emp[emp["jenis_kelamin"] == sex].groupby(band[emp["jenis_kelamin"] == sex], observed=True)["pendapatan_bulanan_idr"]
        got = m.mean() / emp.loc[emp["jenis_kelamin"] == sex, "pendapatan_bulanan_idr"].mean()
        for g, n in m.size().items():
            rows.append({"jenis_kelamin": sex, "kelompok_umur": g, "n": n,
                         "rasio_bps": float(wa.set_index("kelompok_umur").loc[g, key] / avg[key]), "rasio_hasil": float(got[g])})
    t = pd.DataFrame(rows)
    r.table(t)
    big = t[t["n"] >= 200]
    gap = (big["rasio_hasil"] / big["rasio_bps"] - 1).abs().max()
    r.check("profil upah menurut umur", gap <= 0.15,
            f"selisih maks {gap:.1%} dari rasio BPS (kelompok n>=200); toleransi 15% karena ekor log-normal")

    # 3. Banking inclusion vs SNLIK
    r.h("3. Inklusi perbankan per karakteristik vs SNLIK 2025 (diskalakan ke sektor perbankan)")
    scale = ref.snlik("inklusi", "sektor")["Perbankan"] / ref.snlik("inklusi", "nasional")["Indonesia"]
    for dim, col, fn in [("umur", "kelompok_umur", None), ("pekerjaan", "pekerjaan", None),
                         ("pendapatan", "pendapatan_bulanan_idr", income_band)]:
        target = (ref.snlik("inklusi", dim) / 100 * scale).clip(upper=0.99)
        values = fn(pop[col]) if fn else pop[col]
        grp = pop["punya_rekening_bank"].groupby(values.to_numpy())
        t = compare(target, grp.mean(), dim)
        r.table(t)
        # Raking cannot hit every SNLIK margin exactly when the synthetic joint differs
        # from the survey's; allow 2 points plus 3 binomial standard errors.
        se = np.sqrt(t["target"] * (1 - t["target"]) / grp.size().reindex(t[dim]).fillna(1).to_numpy())
        ok = (t["selisih_poin_persen"].abs() / 100 <= 0.02 + 3 * se).all()
        r.check(f"inklusi per {dim}", ok, f"selisih maks {t['selisih_poin_persen'].abs().max():.2f} poin")
    overall = pop["punya_rekening_bank"].mean()
    r.check("inklusi perbankan total", abs(overall - 0.7065) * 100 <= 2, f"{overall:.3f} vs 0.7065")

    # 4. Product levels and movement
    r.h("4. Kepemilikan produk Bank: level, pergerakan, dan korelasi")
    levels = d["levels"]
    m1 = panel[panel["bulan_ke"] == 1][levels["kolom"]].mean()
    mT = panel[panel["bulan_ke"] == ref.cfg["bulan"]][levels["kolom"]].mean()
    lv = levels[["produk", "level_target", "sumber_level"]].copy()
    lv["hasil_bulan_1"], lv["hasil_bulan_terakhir"] = m1.to_numpy(), mT.to_numpy()
    r.table(lv)
    n1 = (panel["bulan_ke"] == 1).sum()
    # Binomial noise: 3 standard errors around the target.
    tol = 3 * np.sqrt(lv["level_target"] * (1 - lv["level_target"]) / n1)
    worst = ((lv["hasil_bulan_1"] - lv["level_target"]).abs() / tol).max()
    r.check("level bulan 1 vs target", worst <= 1, f"selisih terbesar {worst:.2f}x batas 3 standard error")

    # Who holds what: capital-market holders vs KSEI Oct 2025, income gradient for the rest.
    first = panel[panel["bulan_ke"] == 1].drop_duplicates("person_id").merge(
        cust[["person_id", "pendapatan_bulanan_idr"]], on="person_id")
    k = ref.ksei
    for dim, values in [("umur", first["usia"]), ("penghasilan_tahunan", first["pendapatan_bulanan_idr"] * 12)]:
        kd = k[k["dimensi"] == dim]
        band = pd.Series(np.array(kd["kategori"])[np.searchsorted(kd["batas_atas"].to_numpy(), values, side="right")])
        for prod in ["Reksa Dana (agen penjual)", "Bonds"]:
            col = slug(prod)
            got = first[col].groupby(band.to_numpy()).sum() / first[col].sum()
            t = compare(pd.Series(kd["porsi_investor"].to_numpy(), index=kd["kategori"]), got, dim)
            gap = t["selisih_poin_persen"].abs().max()
            r.check(f"pemegang {prod} per {dim} vs KSEI Okt 2025", gap <= 5, f"selisih maks {gap:.2f} poin")
    earn = first[first["pendapatan_bulanan_idr"] > 0]
    q = pd.qcut(earn["pendapatan_bulanan_idr"].rank(method="first"), 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
    rows = []
    for prod in list(ref.cfg["produk"].get("gradien_pendapatan", {})) + ["Reksa Dana (agen penjual)", "Bonds"]:
        rate = earn[slug(prod)].groupby(q.to_numpy(), observed=True).mean()
        rows.append({"produk": prod, **rate.round(4).to_dict()})
    t = pd.DataFrame(rows)
    r.p("Porsi pemegang per kuintil penghasilan (nasabah berpenghasilan, bulan 1):")
    r.table(t)
    rising = (t["Q5"] > t["Q1"]).all()
    r.check("kepemilikan naik dengan penghasilan", rising, "Q5 > Q1 untuk deposito, giro, Prioritas, kartu kredit, reksa dana, bonds")

    churn_target = ref.dyn_products.set_index("kolom_santander")["churn_bulanan"]
    rows = []
    s = panel.sort_values(["person_id", "bulan_ke"])
    for prod, col, analog in zip(levels["produk"], levels["kolom"], levels["analog_santander"]):
        prev = s.groupby("person_id")[col].shift(1)
        same = s.groupby("person_id")["bulan_ke"].diff() == 1
        held = same & (prev == 1)
        events, n = ((s[col] == 0) & held).sum(), held.sum()
        rows.append({"produk": prod, "churn_santander": churn_target[analog], "churn_hasil": events / max(n, 1),
                     "kejadian": int(events), "harapan": churn_target[analog] * n})
    ch = pd.DataFrame(rows)
    r.table(ch)
    # Poisson noise on the number of closures: 3 standard deviations (+2 for tiny counts).
    ok = ((ch["kejadian"] - ch["harapan"]).abs() <= 3 * np.sqrt(ch["harapan"]) + 2).all()
    r.info("churn bulanan vs Santander", ("dalam" if ok else "di luar") + " 3 simpangan baku Poisson")

    last = panel[panel["bulan_ke"] == 1]
    gen_phi = last[levels["kolom"]].corr().to_numpy()
    lat = ref.corr.loc[levels["analog_santander"], levels["analog_santander"]].to_numpy()
    iu = np.triu_indices(len(levels), 1)
    keep = ~np.equal.outer(levels["analog_santander"].to_numpy(), levels["analog_santander"].to_numpy())[iu]
    corr_of_corr = np.corrcoef(np.nan_to_num(gen_phi[iu][keep]), lat[iu][keep])[0, 1]
    r.info("pola kepemilikan bersama vs Santander",
           f"korelasi antar matriks korelasi {corr_of_corr:.2f}; produk berbentuk Indonesia ikut naik bersama penghasilan")

    # 5. Customer flow
    r.h("5. Arus nasabah masuk dan keluar vs Santander (median bulanan)")
    sizes = panel.groupby("bulan_ke").size()
    entries = cust.groupby("bulan_masuk").size().reindex(sizes.index).fillna(0)[1:]
    exits = cust.groupby("bulan_keluar").size().reindex(sizes.index).fillna(0)[:-1]
    entry_rate = (entries / sizes.shift(1)[1:]).median()
    exit_rate = (exits / sizes[:-1]).median()
    r.info("laju masuk vs Santander", f"{entry_rate:.4f} vs {ref.extra('laju_masuk_bulanan_median'):.4f}")
    r.info("laju keluar vs Santander", f"{exit_rate:.4f} vs {ref.extra('laju_keluar_bulanan_median'):.4f}")

    # 6. Value chain structure
    r.h("6. Value chain: struktur jaringan dan transfer")
    comp, rel, tr = d["companies"], d["relations"], d["transfers"]
    anchors = comp.loc[comp["is_anchor"], "company_id"]
    deg = pd.concat([rel["from_id"], rel["to_id"]]).value_counts().reindex(anchors).fillna(0)
    r.p(f"Derajat anchor: min {deg.min():.0f}, median {deg.median():.0f}, maks {deg.max():.0f}; "
        f"5 anchor teratas memegang {deg.nlargest(5).sum() / deg.sum():.1%} relasi.")
    r.check("degree long tail", deg.max() >= 4 * deg.median(), "anchor terbesar >= 4x median")
    rank = {"Mikro": 0, "Kecil": 1, "Menengah": 2, "Besar": 3}
    scale_of = comp.set_index("company_id")["skala"].map(rank)
    b2b = tr[tr["jenis_relasi_terlihat"] != "PAYROLL"].copy()
    b2b["skala"] = np.minimum(b2b["from_id"].map(scale_of), b2b["to_id"].map(scale_of)).map({v: k for k, v in rank.items()})
    med = b2b.groupby("skala")["total_nominal_rp"].median().reindex(list(rank))
    r.p("Median nominal transfer per skala pihak yang lebih kecil: " + ", ".join(f"{k} Rp{v:,.0f}" for k, v in med.items()))
    r.check("nominal naik sesuai skala", med.is_monotonic_increasing, "Mikro < Kecil < Menengah < Besar")
    skew = b2b["total_nominal_rp"].skew()
    r.check("nominal miring ke kanan", skew > 1, f"skewness {skew:.1f}")
    pay = tr[tr["jenis_relasi_terlihat"] == "PAYROLL"].groupby("bulan_ke")["total_nominal_rp"].sum()
    thr_months = ref.calendar.loc[ref.calendar["bulan_thr"] == 1, "bulan_ke"]
    lift = pay[thr_months].mean() / pay.drop(thr_months).median()
    r.check("lonjakan payroll saat THR", 1.8 <= lift <= 2.2, f"payroll bulan THR = {lift:.2f}x bulan biasa (THR 1x upah)")
    unknown = (rel["jenis_relasi_terlihat"] == "UNKNOWN").mean()
    r.check("porsi relasi UNKNOWN", abs(unknown - ref.cfg["value_chain"]["porsi_relasi_tidak_diketahui"]) <= 0.03, f"{unknown:.3f}")

    # 7. Consistency rules
    r.h("7. Aturan konsistensi")
    persons, emp = d["persons"], d["employment"]
    payroll_people = set(panel.loc[panel[slug("Bank Payroll")] == 1, "person_id"])
    employer_bank = emp[emp["peran"] == "KARYAWAN"].merge(comp[["company_id", "bank_payroll"]], on="company_id")
    bad = employer_bank[employer_bank["person_id"].isin(payroll_people) & (employer_bank["bank_payroll"] != "Bank")]
    r.check("pemegang Bank Payroll bekerja di perusahaan payroll Bank", len(bad) == 0, f"{len(bad)} pelanggaran")
    customers_set = set(persons.loc[persons["is_bank_customer"] == 1, "person_id"])
    non_payroll_at_bank = employer_bank[employer_bank["person_id"].isin(customers_set)
                                       & ~employer_bank["person_id"].isin(payroll_people) & (employer_bank["bank_payroll"] == "Bank")]
    r.check("nasabah Bank di perusahaan payroll Bank memegang Bank Payroll", len(non_payroll_at_bank) == 0,
            f"{len(non_payroll_at_bank)} pelanggaran")
    prospect_bank = employer_bank[~employer_bank["person_id"].isin(customers_set)].merge(persons[["person_id", "bank_utama"]], on="person_id")
    bad_prospect = int(((prospect_bank["bank_utama"] == "Bank") | (prospect_bank["bank_utama"] == "TIDAK ADA")).sum())
    r.check("prospek perorangan digaji ke rekening bank lain", bad_prospect == 0, f"{bad_prospect} pelanggaran")
    traders = emp[emp["peran"] == "PEMBELI"]
    seller_bank = traders["company_id"].map(comp.set_index("company_id")["is_bank_customer"]).eq(1).all()
    trader_bank = persons.set_index("person_id").loc[traders["person_id"], "bank_utama"]
    occ = persons.set_index("person_id").loc[traders["person_id"], "pekerjaan"].eq("Pengusaha/Wiraswasta").all()
    r.check("pedagang membeli dari nasabah Bank, berbank lain, dan berwiraswasta",
            bool(seller_bank and occ and trader_bank.isin(["Bank", "TIDAK ADA"]).sum() == 0),
            f"{len(traders):,} pedagang")
    ids = set(persons["person_id"]) | set(comp["company_id"])
    missing = (~tr["from_id"].isin(ids) | ~tr["to_id"].isin(ids)).sum()
    r.check("semua pihak transfer ada di persons/companies", missing == 0, f"{missing} baris")
    r.check("ID unik", persons["person_id"].is_unique and comp["company_id"].is_unique, "persons dan companies")
    # Every product opening (month 1 holdings and every 0 -> 1 move) must meet the catalog
    # and regulator rules at that moment (e.g. BI: credit card holder 21+ and income >= Rp3 m).
    pm = ref.product_model[ref.product_model["jenis"] == "tambahan"].reset_index(drop=True)
    s = panel.sort_values(["person_id", "bulan_ke"]).merge(
        cust[["person_id", "pekerjaan", "pendapatan_bulanan_idr"]], on="person_id")
    elig = eligibility(pm, s["usia"].to_numpy(), s["pekerjaan"].to_numpy(), s["pendapatan_bulanan_idr"].to_numpy())
    first = s.groupby("person_id").cumcount() == 0
    bad_rows = {}
    for j, name in enumerate(pm["produk"]):
        col = slug(name)
        opened = (s[col] == 1) & (first | (s.groupby("person_id")[col].shift(1) == 0))
        n_bad = int((opened & ~elig[:, j]).sum())
        if n_bad:
            bad_rows[name] = n_bad
    r.check("setiap pembukaan produk memenuhi syarat katalog dan regulator", not bad_rows,
            "0 pelanggaran" if not bad_rows else str(bad_rows))
    cc = s[s[slug("Bank Visa Platinum")] == 1]
    bi_bad = int(((cc["usia"] < 21) | (cc["pendapatan_bulanan_idr"] < 3_000_000)).sum())
    r.check("kartu kredit sesuai BI PADG 32/2025 (21+, pendapatan >= Rp3 juta)", bi_bad == 0, f"{bi_bad} baris")
    minors = s[s["usia"] < 17]
    extra = [slug(n) for n in pm["produk"]]
    minor_bad = int(minors[extra].to_numpy().sum())
    r.check("nasabah < 17 tahun hanya memegang rekening anak", minor_bad == 0, f"{minor_bad} kepemilikan produk lain")

    # 8. Acquisition labels
    r.h("8. Label akuisisi")
    acq, feats = d["acquisitions"], d["features"]
    rows = []
    for k, (a, b) in enumerate(ref.cfg["akuisisi"]["jendela_label"], start=1):
        open_ = acq[(acq["jendela"] == 0) | (acq["jendela"] >= k)]
        hit = open_["jendela"] == k
        rows.append({"jendela": k, "fitur_sampai_bulan": a, "label_bulan": f"{a + 1}-{b}", "kandidat": len(open_),
                     "jadi_nasabah": int(hit.sum()), "perusahaan": int((hit & (open_["tipe"] == "PERUSAHAAN")).sum()),
                     "perorangan": int((hit & (open_["tipe"] == "PERORANGAN")).sum()), "base_rate": hit.mean()})
    t = pd.DataFrame(rows)
    r.table(t)
    r.check("base rate per jendela", t["base_rate"].between(0.03, 0.05).all(),
            ", ".join(f"jendela {k} {v:.3f}" for k, v in zip(t["jendela"], t["base_rate"])) + f" (target {ref.cfg['akuisisi']['base_rate_target']})")
    r.p(f"Kandidat yang terlihat bank: {acq['terlihat_bank'].sum():,} dari {len(acq):,}.")
    last = ref.cfg["akuisisi"]["bulan_fitur_terakhir"]
    test = acq[(acq["terlihat_bank"] == 1) & acq["jendela"].isin([0, len(t)])]
    r.p(signal_check(test, feats[feats["bulan_fitur_terakhir"] == last].drop(columns="bulan_fitur_terakhir"), r))

    # 9. data_bank only holds what a bank could really see (kamus_data.csv)
    r.h("9. Realisme data bank (data_bank/ vs kamus_data.csv)")
    bank = d["data_bank"]
    own_cust = set(bank["companies.csv"].loc[bank["companies.csv"]["is_bank_customer"] == 1, "company_id"]) | \
        set(bank["persons.csv"].loc[bank["persons.csv"]["is_bank_customer"] == 1, "person_id"])
    t = bank["transfers_monthly.csv"]
    hidden_tr = int((~t["from_id"].isin(own_cust) & ~t["to_id"].isin(own_cust)).sum())
    r.check("transfer di data_bank selalu punya sisi Bank", hidden_tr == 0, f"{hidden_tr} baris tanpa sisi Bank")
    from .export import HIDDEN_COMPANY, HIDDEN_PERSON
    c, p = bank["companies.csv"], bank["persons.csv"]
    leak_c = int(c.loc[c["is_bank_customer"] == 0, HIDDEN_COMPANY].notna().to_numpy().sum())
    leak_p = int(p.loc[p["is_bank_customer"] == 0, HIDDEN_PERSON].notna().to_numpy().sum())
    r.check("kolom MERAH kosong untuk non-nasabah", leak_c + leak_p == 0, f"{leak_c + leak_p} sel terisi")
    r.check("pendapatan pasti tidak ada di data_bank", "pendapatan_bulanan_idr" not in bank["nasabah.csv"].columns
            and "pendapatan_bulanan_idr" not in p.columns, "hanya kisaran_pendapatan")
    unseen = set(bank["acquisitions.csv"]["entity_id"]) - (set(t["from_id"]) | set(t["to_id"]))
    r.check("kandidat akuisisi di data_bank terlihat di transfer", not unseen, f"{len(unseen)} tidak terlihat")

    wholesale_checks(ref, d, r)

    # 10. Controlled data-quality problems (config: data_kotor)
    r.h("10. Data kotor terkontrol di data_bank/ (untuk EDA)")
    cfg, log, clean = ref.cfg.get("data_kotor", {}), d.get("catatan_data_kotor", pd.DataFrame()), d.get("data_bank_bersih", {})
    if not cfg.get("aktif") or log.empty:
        r.p("Data kotor tidak aktif: data_bank/ bersih.")
        return r
    rows, ok = [], True
    for name, spec in cfg.items():
        if name == "aktif":
            continue
        n = len(clean[name])
        for kind, label in [("hilang", "hilang"), ("variasi_teks", "variasi_teks"), ("outlier", "outlier")]:
            for col, rate in spec.get(kind, {}).items():
                got = int(((log["file"] == name) & (log["kolom"] == col) & (log["jenis"] == label)).sum())
                # Variants and outliers are drawn from cells still filled after the missing step.
                emptied = int(round(n * spec.get("hilang", {}).get(col, 0)))
                base = n if kind == "hilang" else int(clean[name][col].notna().sum()) - emptied
                want = int(round(base * rate))
                rows.append({"file": name, "kolom": col, "jenis": label, "porsi_config": rate, "ditanam": got})
                ok &= got == want
        if spec.get("duplikat_baris"):
            got = int(((log["file"] == name) & (log["jenis"] == "duplikat")).sum())
            rows.append({"file": name, "kolom": "(baris)", "jenis": "duplikat", "porsi_config": spec["duplikat_baris"], "ditanam": got})
            ok &= got == int(round(n * spec["duplikat_baris"])) and len(bank[name]) == n + got
    r.table(pd.DataFrame(rows))
    r.check("jumlah masalah yang ditanam sesuai config dan tercatat", ok, f"{len(log):,} perubahan di kunci_evaluasi/catatan_data_kotor.csv")
    return r


def signal_check(acq: pd.DataFrame, feats: pd.DataFrame, r: Report) -> str:
    """Graph features should carry most of the signal, and the label must not be trivial."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import cross_val_predict
    except ImportError:
        return "scikit-learn tidak terpasang: cek sinyal graph dilewati."
    # Only features a bank could really have: graph features from visible transfers and
    # the sector from public company registries (kamus_data.csv).
    df = acq.merge(feats, on="entity_id")
    y = (df["bulan_jadi_nasabah"] > 0).astype(int)
    graph = df[["log_nominal_dengan_bank", "porsi_tetangga_bank", "lama_relasi_bulan", "porsi_bank_dua_langkah"]]
    table = pd.get_dummies(df["sektor"], prefix="sektor", dtype=float)
    auc = {}
    for name, X in [("tabel saja (sektor)", table), ("graph saja", graph), ("graph + tabel", pd.concat([graph, table], axis=1))]:
        pred = cross_val_predict(LogisticRegression(max_iter=1000), X, y, cv=5, method="predict_proba")[:, 1]
        auc[name] = roc_auc_score(y, pred)
    r.check("graph lebih kuat dari tabel", auc["graph saja"] > auc["tabel saja (sektor)"],
            ", ".join(f"AUC {k} {v:.3f}" for k, v in auc.items()))
    r.check("label tidak terlalu mudah", auc["graph + tabel"] < 0.95, f"AUC {auc['graph + tabel']:.3f} < 0.95")
    return ""


def wholesale_checks(ref: Ref, d: dict, r: Report):
    """11. Wholesale layer (Guideline section 14): BI channel limits, Bank side, facilities,
    product dates, RM portfolio size, contacts only for CIF, label window and difficulty."""
    r.h("11. Data wholesale (interview RM dan PS)")
    cfg, ws, T = ref.cfg["wholesale"], d["wholesale"], ref.cfg["bulan"]
    comp, tx = ws["companies"], ws["transaksi"]
    seg = comp[comp["is_bank_customer"] == 1]["segmen_bank"].value_counts()
    r.p("Nasabah Bank per segmen: " + ", ".join(f"{k} {v:,}" for k, v in seg.items()))
    avg = tx["total_nominal_rp"] / tx["jumlah_transaksi"].clip(lower=1)
    bad = int(((tx["channel"] == "BI-FAST") & (avg > cfg["batas_bifast"])).sum()
              + ((tx["channel"] == "SKN") & (avg > cfg["batas_skn"])).sum()
              + ((tx["channel"] == "RTGS") & (avg <= cfg["batas_bawah_rtgs"])).sum())
    r.check("channel sesuai batas Bank Indonesia", bad == 0,
            f"{bad} baris melanggar (BI-FAST <= Rp250 jt, SKN <= Rp1 M, RTGS > Rp100 jt)")
    r.table(tx.groupby("kelas_nama_bank")["total_nominal_rp"].agg(["size", "sum"]).reset_index()
            .rename(columns={"size": "baris", "sum": "total_nominal_rp"}))
    own_cust = set(comp.loc[comp["is_bank_customer"] == 1, "company_id"])
    r.check("setiap transaksi counterparty milik nasabah Bank", bool(tx["company_id"].isin(own_cust).all()),
            f"{int((~tx['company_id'].isin(own_cust)).sum())} baris")

    fac, labels = ws["fasilitas"], ws["label"]
    became = set(labels.loc[labels["label"] == "non_debitur_ke_debitur", "company_id"])
    debt = set(comp.loc[comp["status_debitur_awal"] == 1, "company_id"]) | became
    r.check("fasilitas hanya untuk debitur", bool(fac["company_id"].isin(debt).all()),
            f"{int((~fac['company_id'].isin(debt)).sum())} baris")
    founded = comp.set_index("company_id")["tahun_berdiri"]
    fstart = pd.to_datetime(fac["tanggal_mulai"])
    age = fstart.dt.year - fac["company_id"].map(founded)
    new = fstart >= pd.Timestamp(ref.calendar["bulan"].iloc[0])
    early = int((fac["produk"].isin(["Kredit Modal Kerja", "Kredit Investasi"]) & (age < cfg["usaha_min_tahun"]) & new).sum())
    r.check("KMK/KI baru hanya untuk usaha >= 3 tahun (katalog)", early == 0, f"{early} baris")
    seg = fac["company_id"].map(comp.set_index("company_id")["segmen_bank"])
    kur = fac["produk"].str.startswith("KUR")
    kur_bad = int(((kur != seg.eq("UMKM")) | (kur & (fac["plafon_rp"] > cfg["batas_kur_kecil"]))
                   | ((fac["produk"] == "KUR Mikro") & (fac["plafon_rp"] > cfg["batas_kur_mikro"]))).sum())
    r.check("KUR hanya untuk UMKM dan sesuai batas plafon", kur_bad == 0, f"{kur_bad} baris; {int(kur.sum())} fasilitas KUR")

    h = ws["riwayat_produk"]
    start = pd.to_datetime(h["tanggal_mulai"])
    end = pd.to_datetime(h["tanggal_selesai"].where(h["tanggal_selesai"] != ""))
    panel_end = pd.Timestamp(ref.calendar["bulan"].iloc[-1]) + pd.offsets.MonthEnd(0)
    bad = int(((end.notna() & (end < start)) | (start > panel_end) | (end.notna() != (h["status"] == "TIDAK AKTIF"))).sum())
    r.check("tanggal dan status riwayat produk konsisten", bad == 0, f"{bad} baris")
    n_cat = int(h["no_katalog"].isin(pd.to_numeric(ref.catalog["No"], errors="coerce")).sum())
    r.check("produk wholesale ada di katalog Bank", n_cat == len(h), f"{len(h) - n_cat} baris tanpa nomor katalog")

    pf = ws["rm_portofolio"]
    per = pf.groupby("rm_id")["status_debitur_awal"].agg(["sum", "size"])
    full = per[per["size"] == cfg["debitur_per_rm"] + cfg["non_debitur_per_rm"]]
    mean_d = full["sum"].mean() if len(full) else float("nan")
    r.check("debitur per RM sesuai interview", abs(mean_d - cfg["debitur_per_rm"]) <= 4,
            f"rata-rata {mean_d:.1f} debitur dan {(full['size'] - full['sum']).mean():.1f} non-debitur per RM "
            f"({len(per)} RM; target {cfg['debitur_per_rm']} dan {cfg['non_debitur_per_rm']})")
    pic = int(((comp["is_bank_customer"] == 0) & (comp["ada_pic_terdaftar"] == 1)).sum())
    r.check("kontak hanya untuk perusahaan ber-CIF", pic == 0, f"{pic} perusahaan non-nasabah dengan PIC")

    names = ["non_debitur_ke_debitur", "cross_sell_wholesale", "reaktivasi", "leakage"]
    t = labels.groupby(["label", "jendela"]).size().unstack(fill_value=0).reindex(names, fill_value=0)
    t = t.rename(columns=lambda k: f"jendela_{k}").reset_index()
    t["base_rate_config"] = [cfg["label"][n] for n in names]
    r.table(t)
    windows = ref.cfg["akuisisi"]["jendela_label"]
    inside = all(labels.loc[labels["jendela"] == k, "bulan_ke"].between(a + 1, b).all()
                 for k, (a, b) in enumerate(windows, start=1))
    r.check("label wholesale hanya di bulan jendelanya", bool(inside), ", ".join(f"jendela {k}: bulan {a + 1}-{b}"
                                                                              for k, (a, b) in enumerate(windows, start=1)))
    low = t.set_index("label").drop(columns="base_rate_config").min(axis=1)
    r.check(f"minimal {cfg['label_min_per_jendela']} label wholesale per jendela", bool((low >= cfg["label_min_per_jendela"]).all()),
            ", ".join(f"{k} {v}" for k, v in low.items()))
    r.p(wholesale_signal(ref, ws, r))


def wholesale_signal(ref, ws, r: Report) -> str:
    """Test-window labels must be learnable from bank-visible features but not trivial."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import cross_val_predict
    except ImportError:
        return "scikit-learn tidak terpasang: cek sinyal wholesale dilewati."
    last = ref.cfg["akuisisi"]["bulan_fitur_terakhir"]
    c, lab = ws["companies"], ws["label"]
    k = len(ref.cfg["akuisisi"]["jendela_label"])
    f_all = ws["fitur"][ws["fitur"]["bulan_fitur_terakhir"] == last].drop(columns="bulan_fitur_terakhir").set_index("company_id")
    own_cust = c[c["is_bank_customer"] == 1]
    before = lambda name: set(lab.loc[(lab["label"] == name) & (lab["jendela"] < k), "company_id"])
    # Each label is scored on the companies that could still get it in the test window.
    pools = {"non_debitur_ke_debitur": own_cust[(own_cust["status_debitur_awal"] == 0) & ~own_cust["company_id"].isin(before("non_debitur_ke_debitur"))],
             "cross_sell_wholesale": own_cust,
             "leakage": own_cust[(own_cust["punya_rekening_bank_lain"] == 1) & ~own_cust["company_id"].isin(before("leakage"))]}
    out = []
    for name, pool in pools.items():
        f = f_all.loc[pool["company_id"]].fillna(0)
        y = f.index.isin(lab.loc[(lab["label"] == name) & (lab["jendela"] == k), "company_id"]).astype(int)
        if y.sum() < 10:
            continue
        pred = cross_val_predict(LogisticRegression(max_iter=1000), f, y, cv=5, method="predict_proba")[:, 1]
        out.append((name, roc_auc_score(y, pred)))
    ok = all(0.55 < a < 0.95 for _, a in out)
    r.check("label wholesale bisa dipelajari tapi tidak terlalu mudah", ok,
            ", ".join(f"AUC {n} {a:.3f}" for n, a in out) + " (jendela test; target 0,55-0,95)")
    return ""
