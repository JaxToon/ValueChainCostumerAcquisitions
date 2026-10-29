"""Wholesale layer seen by an RM Transactional (interview RM and Product Specialist,
Oct 2026; Guideline Data Sintetis section 14): Bank segment, RM portfolio, transactions
with counterparty name and bank, balances, wholesale product history, financing
facilities, an incomplete Bisdev lead file, and wholesale labels.

Sourced: product names and numbers and who they are for (Bank catalog), payment channel
limits (Bank Indonesia: BI-FAST <= Rp250 jt, SKN <= Rp1 M, RTGS > Rp100 jt), KMK/KI only
for businesses running >= 3 years (catalog), segment cut-offs and RM portfolio size
(interview, to be confirmed). Everything else is an assumption in config.yaml (wholesale).
"""
import numpy as np
import pandas as pd
from scipy.special import expit

from .value_chain import OTHER_BANKS

TRADE = "transaksi"


def build(ref, comp: pd.DataFrame, rel: pd.DataFrame, transfers: pd.DataFrame, rng: np.random.Generator) -> dict:
    cfg, T = ref.cfg["wholesale"], ref.cfg["bulan"]
    windows = ref.cfg["akuisisi"]["jendela_label"]
    last = ref.cfg["akuisisi"]["bulan_fitur_terakhir"]
    cal = ref.calendar.set_index("bulan_ke")["bulan"]
    panel_start = pd.Timestamp(cal[1])
    panel_end = pd.Timestamp(cal[T]) + pd.offsets.MonthEnd(0)

    comp = add_segment(ref, comp, rng)
    switch = bank_switches(cfg, comp, rng, T)
    tx = counterparty_transactions(ref, comp, transfers, switch, rng)

    # History before the first label window; every later adoption is a label.
    first_last = windows[0][0]
    hist = product_history(ref, comp, features(comp, rel, tx, first_last), rng, panel_start, first_last, cal)
    fac = facilities(ref, comp, rel, rng, cal)

    lab_cfg = cfg["label"]
    own_cust = comp[comp["is_bank_customer"] == 1].set_index("company_id")
    umkm = own_cust["segmen_bank"].eq("UMKM")
    catalogs = {True: pd.DataFrame(cfg["produk_umkm"]), False: pd.DataFrame(cfg["produk_wholesale"])}
    debtor = set(own_cust.index[own_cust["status_debitur_awal"] == 1])
    reactivated, leak_month, labels, feats = set(), {}, [], []

    for k, (w_last, w_end) in enumerate(windows, start=1):
        window = np.arange(w_last + 1, w_end + 1)
        cutoff = pd.Timestamp(cal[w_last]) + pd.offsets.MonthEnd(0)
        now = hist[pd.to_datetime(hist["tanggal_mulai"]) <= cutoff]
        feat = features(comp, rel, tx, w_last)
        product_features(feat, now)
        feats.append(feat.assign(bulan_fitur_terakhir=w_last))
        z = standardize(feat.reindex(own_cust.index).fillna(0))
        age = pd.Timestamp(cal[w_last]).year - own_cust["tahun_berdiri"]
        old_enough = np.where(umkm, age >= cfg["usaha_min_tahun_kur"], age >= cfg["usaha_min_tahun"])

        # Non-debtor -> debtor: KUR for UMKM, KMK or KI otherwise (catalog age rules).
        cand = ~own_cust.index.isin(debtor) & old_enough
        score = 0.8 * z["log_saldo"] + 0.6 * z["log_nominal_masuk"] + 0.5 * z["mitra_anchor_bank"] + 0.4 * z["segmen_rank"]
        for cid in draw_label(score[cand], lab_cfg["non_debitur_ke_debitur"], lab_cfg["noise_sd"], rng):
            m = int(rng.choice(window))
            row = new_facility(ref, own_cust.loc[cid], m, cal, rng)
            fac.append(row)
            debtor.add(cid)
            labels.append((cid, "non_debitur_ke_debitur", m, row["produk"], k))

        # Cross-sell: a product the company does not hold yet (UMKM: QRIS/EDC; others: wholesale).
        held = now.groupby("company_id")["produk"].apply(set)
        score = 0.7 * z["n_pembayar"] + 0.5 * z["log_saldo"] + 0.5 * z["jumlah_produk"] + 0.4 * z["segmen_rank"]
        added = []
        for cid in draw_label(score, lab_cfg["cross_sell_wholesale"], lab_cfg["noise_sd"], rng):
            pm = catalogs[bool(umkm[cid])]
            pr = trigger_probs(cfg, pm, own_cust.loc[cid], feat.loc[cid])
            pr[pm["produk"].isin(held.get(cid, set())).to_numpy()] = 0
            if pr.sum() == 0:
                continue
            j = rng.choice(len(pm), p=pr / pr.sum())
            m = int(rng.choice(window))
            added.append(history_row(ref, own_cust.loc[cid], pm.iloc[j], month_date(cal, m, rng), panel_end, rng))
            labels.append((cid, "cross_sell_wholesale", m, pm.at[j, "produk"], k))

        # Reactivation: a transaction product (L/C, SKBDN, SBLC, Garansi Bank) that had ended.
        ended = now[(now["jenis"] == TRADE) & (now["tanggal_selesai"] != "")]
        ended = ended[(pd.to_datetime(ended["tanggal_selesai"]) <= cutoff) & ~ended["company_id"].isin(reactivated)]
        ended = ended.sort_values("tanggal_selesai").drop_duplicates("company_id", keep="last").set_index("company_id")
        score = 0.7 * z["log_nominal_masuk"] + 0.6 * z["kontraktor"] + 0.4 * z["segmen_rank"]
        pmw = catalogs[False]
        for cid in draw_label(score[ended.index], lab_cfg["reaktivasi"], lab_cfg["noise_sd"], rng):
            m = int(rng.choice(window))
            prod = pmw[pmw["produk"] == ended.at[cid, "produk"]].iloc[0]
            added.append(history_row(ref, own_cust.loc[cid], prod, month_date(cal, m, rng), panel_end, rng))
            reactivated.add(cid)
            labels.append((cid, "reaktivasi", m, prod["produk"], k))
        if added:
            hist = pd.concat([hist, pd.DataFrame(added)], ignore_index=True)

        # Leakage: money to the company's own account at another bank rises and stays.
        cand = (own_cust["punya_rekening_bank_lain"] == 1) & ~own_cust.index.isin(list(leak_month))
        debt_now = pd.Series(own_cust.index.isin(debtor).astype(int), index=own_cust.index)
        # ASUMSI: larger firms bank with several banks more often, so leakage rises with segment.
        score = 0.8 * z["porsi_ke_rekening_sendiri"] + 0.6 * (1 - debt_now) - 0.4 * z["jumlah_produk"] + 0.8 * z["segmen_rank"]
        for cid in draw_label(score[cand], lab_cfg["leakage"], lab_cfg["noise_sd"], rng):
            m = int(rng.choice(window))
            leak_month[cid] = m
            labels.append((cid, "leakage", m, "", k))

    hist = hist.sort_values(["company_id", "tanggal_mulai"]).reset_index(drop=True)
    fac = pd.DataFrame(fac)
    leak_month = pd.Series(leak_month, dtype=float)
    up = tx["company_id"].map(leak_month)
    boost = (tx["kelas_nama_bank"] == "NAMA_SAMA_BANK_BEDA") & (tx["arah"] == "KELUAR") & (tx["bulan_ke"] >= up)
    tx.loc[boost, "total_nominal_rp"] = np.round(tx.loc[boost, "total_nominal_rp"] * cfg["leakage_pengali_dana_keluar"], -3)
    tx = assign_channel(cfg, tx, rng)

    bal = balances(ref, comp, leak_month, rng, cal)
    portfolio = rm_portfolio(cfg, comp)
    leads, lead_truth = bisdev_leads(ref, comp, rel, transfers, rng, cal, last)
    labels = pd.DataFrame(labels, columns=["company_id", "label", "bulan_ke", "produk", "jendela"])
    labels.insert(3, "bulan", labels["bulan_ke"].map(cal))
    feats = pd.concat(feats).rename_axis("company_id").reset_index()

    # Counterparties that switched bank: the company table shows the latest bank seen.
    comp.loc[comp["company_id"].isin(switch.index), "bank_utama"] = comp["company_id"].map(switch["bank_baru"])
    return {"companies": comp, "rm_portofolio": portfolio, "transaksi": tx, "saldo": bal, "riwayat_produk": hist,
            "fasilitas": fac, "lead_bisdev": leads, "lead_bisdev_kunci": lead_truth, "label": labels,
            "pindah_bank": switch.reset_index(), "fitur": feats}


def product_features(feat: pd.DataFrame, hist: pd.DataFrame):
    """Products held at the end of the feature window (history up to that month)."""
    feat["jumlah_produk"] = hist.groupby("company_id").size().reindex(feat.index).fillna(0)
    feat["kontraktor"] = hist[hist["produk"] == "Garansi Bank"].groupby("company_id").size().reindex(feat.index).fillna(0).clip(upper=1)


def add_segment(ref, comp: pd.DataFrame, rng) -> pd.DataFrame:
    """Bank segment from turnover, debtor status at month 1, CIF, PIC flag, own accounts."""
    cfg = ref.cfg["wholesale"]
    comp = comp.copy()
    cut = cfg["segmen_batas_omzet"]
    names = list(cut)
    comp["segmen_bank"] = np.array(names)[np.searchsorted(np.array([float(v) for v in cut.values()]), comp["omzet_tahunan_rp"], side="right") - 1]
    own_cust = comp["is_bank_customer"].to_numpy() == 1
    n = len(comp)
    comp["cif"] = np.where(own_cust, [f"CIF{9000000 + i:07d}" for i in range(n)], "")
    debt = rng.random(n) < comp["segmen_bank"].map(cfg["peluang_debitur"]).to_numpy()
    old_enough = (pd.Timestamp(ref.calendar["bulan"].iloc[0]).year - comp["tahun_berdiri"]) >= cfg["usaha_min_tahun"]
    comp["status_debitur_awal"] = np.where(own_cust, (debt & old_enough).astype(int), 0)
    comp["ada_pic_terdaftar"] = np.where(own_cust, (rng.random(n) < cfg["peluang_pic_terdaftar"]).astype(int), 0)
    comp["punya_rekening_bank_lain"] = np.where(own_cust, (rng.random(n) < cfg["porsi_punya_rekening_bank_lain"]).astype(int), 0)
    comp["punya_beberapa_rekening_bank"] = np.where(own_cust, (rng.random(n) < cfg["porsi_punya_beberapa_rekening_bank"]).astype(int), 0)
    comp["bank_lain_sendiri"] = np.where(comp["punya_rekening_bank_lain"] == 1, rng.choice(OTHER_BANKS, n), "")

    # RM assignment: companies in RM segments, sorted by province, cut into portfolios.
    size = cfg["debitur_per_rm"] + cfg["non_debitur_per_rm"]
    comp["rm_id"], comp["cabang"] = "", np.where(own_cust, "KC " + comp["provinsi"], "")
    k = 0
    for seg in cfg["segmen_dengan_rm"]:
        idx = comp.index[own_cust & (comp["segmen_bank"] == seg)]
        idx = comp.loc[idx].sort_values(["provinsi", "company_id"]).index
        for start in range(0, len(idx), size):
            chunk = idx[start:start + size]
            comp.loc[chunk, "rm_id"] = f"RM{k:03d}"
            comp.loc[chunk, "cabang"] = "KC " + comp.loc[chunk, "provinsi"].mode().iloc[0]
            k += 1
    return comp


def bank_switches(cfg, comp, rng, T) -> pd.DataFrame:
    """A few non-nasabah counterparties move to another bank mid-panel (a visible signal)."""
    non = comp[comp["is_bank_customer"] == 0]
    pick = non.sample(frac=cfg["porsi_counterparty_pindah_bank"], random_state=int(rng.integers(1 << 31)))
    new = [rng.choice([b for b in OTHER_BANKS if b != old]) for old in pick["bank_utama"]]
    return pd.DataFrame({"bank_lama": pick["bank_utama"].to_numpy(), "bank_baru": new,
                         "bulan_pindah": rng.integers(3, T + 1, len(pick))}, index=pick["company_id"].to_numpy())


def counterparty_transactions(ref, comp, transfers, switch, rng) -> pd.DataFrame:
    """One row per Bank company x counterparty x month x direction: company-to-company
    transfers seen from the Bank side, plus money moved between the company's own accounts."""
    cfg, T = ref.cfg["wholesale"], ref.cfg["bulan"]
    c = comp.set_index("company_id")
    own_cust = set(c.index[c["is_bank_customer"] == 1])
    cc = transfers[transfers["from_id"].str.startswith("C") & transfers["to_id"].str.startswith("C")]
    out = cc[cc["from_id"].isin(own_cust)].rename(columns={"from_id": "company_id", "to_id": "counterparty_id"}).assign(arah="KELUAR")
    inn = cc[cc["to_id"].isin(own_cust)].rename(columns={"to_id": "company_id", "from_id": "counterparty_id"}).assign(arah="MASUK")
    tx = pd.concat([out, inn], ignore_index=True)[["bulan_ke", "company_id", "counterparty_id", "arah", "jumlah_transaksi", "total_nominal_rp"]]

    bank = tx["counterparty_id"].map(c["bank_utama"])
    sw = tx["counterparty_id"].map(switch["bulan_pindah"])
    moved = tx["bulan_ke"] >= sw
    bank = bank.where(~moved, tx["counterparty_id"].map(switch["bank_baru"]))
    tx["counterparty_nama"] = tx["counterparty_id"].map(c["nama_samaran"])
    tx["counterparty_bank"] = np.where(bank == "Bank", "Bank", bank)

    # Own accounts: at another bank (nama sama, bank beda) and between Bank accounts.
    rows = []
    monthly = c["omzet_tahunan_rp"] / 12
    for flag, lo_hi, bank_of, n_per in [("punya_rekening_bank_lain", cfg["porsi_omzet_ke_rekening_sendiri"], c["bank_lain_sendiri"], 2),
                                        ("punya_beberapa_rekening_bank", cfg["porsi_omzet_pindah_antar_rekening_bank"], None, 4)]:
        ids = c.index[c[flag] == 1]
        share = rng.uniform(*lo_hi, len(ids))
        for t in range(1, T + 1):
            amt = np.round(monthly[ids].to_numpy() * share * np.exp(rng.normal(0, 0.2, len(ids))), -3)
            for arah, f in [("KELUAR", 1.0), ("MASUK", 0.5)]:
                rows.append(pd.DataFrame({"bulan_ke": t, "company_id": ids, "counterparty_id": ids, "arah": arah,
                                          "jumlah_transaksi": 1 + rng.poisson(n_per, len(ids)),
                                          "total_nominal_rp": np.round(amt * f, -3),
                                          "counterparty_nama": c.loc[ids, "nama_samaran"].to_numpy(),
                                          "counterparty_bank": bank_of[ids].to_numpy() if bank_of is not None else "Bank"}))
    tx = pd.concat([tx, *rows], ignore_index=True)
    same_name = tx["counterparty_id"] == tx["company_id"]
    same_bank = tx["counterparty_bank"] == "Bank"
    tx["kelas_nama_bank"] = np.select([same_name & same_bank, same_name, same_bank],
                                      ["NAMA_SAMA_BANK_SAMA", "NAMA_SAMA_BANK_BEDA", "NAMA_BEDA_BANK_SAMA"], "NAMA_BEDA_BANK_BEDA")
    cal = ref.calendar.set_index("bulan_ke")["bulan"]
    tx.insert(1, "bulan", tx["bulan_ke"].map(cal))
    return tx.sort_values(["bulan_ke", "company_id", "arah", "counterparty_id"]).reset_index(drop=True)


def assign_channel(cfg, tx, rng) -> pd.DataFrame:
    """Dominant channel of the row from the average amount per transaction and BI limits."""
    avg = tx["total_nominal_rp"] / tx["jumlah_transaksi"].clip(lower=1)
    u = rng.random(len(tx))
    small = avg <= cfg["batas_bawah_rtgs"]
    mid = (avg > cfg["batas_bawah_rtgs"]) & (avg <= cfg["batas_skn"])
    ch = np.where(small, np.where(u < cfg["peluang_bifast_sampai_100jt"], "BI-FAST", "SKN"),
                  np.where(mid, np.where(u < cfg["peluang_rtgs_100jt_sampai_1m"], "RTGS", "SKN"), "RTGS"))
    tx["channel"] = np.where(tx["counterparty_bank"] == "Bank", "PEMINDAHBUKUAN", ch)
    return tx


def features(comp, rel, tx, last) -> pd.DataFrame:
    """Per Bank company, feature-window facts the bank can see (drive products and labels)."""
    c = comp.set_index("company_id")
    w = tx[tx["bulan_ke"] <= last]
    other = w[w["counterparty_id"] != w["company_id"]]
    f = pd.DataFrame(index=c.index)
    f["log_nominal_masuk"] = np.log1p(other[other["arah"] == "MASUK"].groupby("company_id")["total_nominal_rp"].sum()).reindex(f.index).fillna(0)
    f["n_pembayar"] = other[other["arah"] == "MASUK"].groupby("company_id")["counterparty_id"].nunique().reindex(f.index).fillna(0)
    f["n_penerima"] = other[other["arah"] == "KELUAR"].groupby("company_id")["counterparty_id"].nunique().reindex(f.index).fillna(0)
    out_all = w[w["arah"] == "KELUAR"].groupby("company_id")["total_nominal_rp"].sum()
    own = w[(w["kelas_nama_bank"] == "NAMA_SAMA_BANK_BEDA") & (w["arah"] == "KELUAR")].groupby("company_id")["total_nominal_rp"].sum()
    f["porsi_ke_rekening_sendiri"] = (own / out_all).reindex(f.index).fillna(0)
    f["log_saldo"] = np.log1p(c["omzet_tahunan_rp"] / 12)
    rank = {"UMKM": 0, "RCC": 1, "Commercial": 2, "Corporate": 3}
    f["segmen_rank"] = c["segmen_bank"].map(rank)
    anchors_bank = set(c.index[c["is_anchor"] & (c["is_bank_customer"] == 1)])
    linked = set(rel.loc[rel["from_id"].isin(anchors_bank), "to_id"]) | set(rel.loc[rel["to_id"].isin(anchors_bank), "from_id"])
    f["mitra_anchor_bank"] = f.index.isin(linked - anchors_bank).astype(float)
    f["kontraktor"] = 0.0
    f["jumlah_produk"] = 0.0
    return f


def trigger_probs(cfg, pm, row, feat_row) -> np.ndarray:
    on = {
        "saldo_tinggi": feat_row["log_saldo"] >= np.log1p(1e9),
        "banyak_pembayar": feat_row["n_pembayar"] >= 5,
        "banyak_penerima": feat_row["n_penerima"] >= 5,
        "sektor_ekspor": row["sektor"] in cfg["sektor_ekspor"],
        "sektor_impor": row["sektor"] in cfg["sektor_impor"],
        "sektor_dagang": row["sektor"] in cfg["sektor_dagang"],
        "kontraktor": row["sektor"] in cfg["sektor_kontraktor"] or row["peran"] == "SUPPLIER",
        "segmen_besar": row["segmen_bank"] == "Corporate",
        "banyak_rekening_bank": row["punya_beberapa_rekening_bank"] == 1,
        "sektor_ritel": row["sektor"] in cfg.get("sektor_ritel", []),
    }
    p = pm["peluang"].to_numpy(float) * np.where([on[t] for t in pm["pemicu"]], pm["pengali"].to_numpy(float), 1.0)
    return np.minimum(p, 0.95)


def product_history(ref, comp, feat, rng, panel_start, last, cal) -> pd.DataFrame:
    """Products each Bank company used up to the end of month `last`, with dates, status,
    beneficiary and project value. UMKM companies draw from the UMKM list (QRIS, EDC),
    others from the wholesale list. Account products stay active unless closed;
    transaction products (L/C, SKBDN, SBLC, Garansi Bank) run for one project and end."""
    cfg = ref.cfg["wholesale"]
    lists = {True: pd.DataFrame(cfg["produk_umkm"]), False: pd.DataFrame(cfg["produk_wholesale"])}
    c = comp[comp["is_bank_customer"] == 1].set_index("company_id")
    cutoff = pd.Timestamp(cal[last]) + pd.offsets.MonthEnd(0)
    panel_end = pd.Timestamp(cal[ref.cfg["bulan"]]) + pd.offsets.MonthEnd(0)
    rows = []
    for cid, r in c.iterrows():
        pm = lists[r["segmen_bank"] == "UMKM"]
        p = trigger_probs(cfg, pm, r, feat.loc[cid])
        for j in np.flatnonzero(rng.random(len(pm)) < p):
            lo = pd.Timestamp(year=max(int(r["tahun_berdiri"]), cfg["tahun_riwayat_mulai"]), month=1, day=1)
            start = lo + (cutoff - lo) * rng.random()
            rows.append(history_row(ref, r, pm.iloc[j], start, panel_end, rng, cid))
    # Account products already in the company table (Tabungan Plus Bisnis, Giro, CIB, Payroll, SCF via anchor)
    for cid, r in c.iterrows():
        for name in filter(None, str(r["produk_bank"]).split(";")):
            rows.append({"company_id": cid, "produk": name, "no_katalog": catalog_no(ref, name), "jenis": "rekening",
                         "tanggal_mulai": (panel_start - pd.Timedelta(days=int(rng.integers(30, 3000)))).date().isoformat(),
                         "tanggal_selesai": "", "status": "AKTIF", "beneficiary_id": "", "nilai_proyek_rp": np.nan,
                         "konteks": "Rekening dan layanan transaksi"})
    return pd.DataFrame(rows)


def history_row(ref, r, prod, start, panel_end, rng, cid=None) -> dict:
    cfg = ref.cfg["wholesale"]
    cid = cid if cid is not None else r.name
    start = pd.Timestamp(start)
    if prod["jenis"] == TRADE:
        end = start + pd.DateOffset(months=int(rng.integers(*cfg["durasi_produk_transaksi_bulan"], endpoint=True)))
        value = round(float(r["omzet_tahunan_rp"]) * rng.uniform(*cfg["nilai_proyek_porsi_omzet"]), -6)
        bene = beneficiary(r, rng)
        ctx = {"Garansi Bank": "Jaminan pelaksanaan proyek", "SBLC": "Jaminan kontrak"}.get(prod["produk"], "Transaksi dagang")
    else:
        end = start + pd.DateOffset(months=int(rng.integers(12, 120))) if rng.random() < cfg["peluang_tutup_produk_rekening"] else None
        value, bene, ctx = np.nan, "", "Rekening dan layanan transaksi"
    ended = end is not None and end <= panel_end
    return {"company_id": cid, "produk": prod["produk"], "no_katalog": int(prod["no_katalog"]), "jenis": prod["jenis"],
            "tanggal_mulai": start.date().isoformat(), "tanggal_selesai": end.date().isoformat() if ended else "",
            "status": "TIDAK AKTIF" if ended else "AKTIF", "beneficiary_id": bene, "nilai_proyek_rp": value, "konteks": ctx}


def beneficiary(r, rng) -> str:
    """Who the guarantee or L/C is for: an anchor for its partners, otherwise a project owner
    outside the dataset (pseudonymous id)."""
    if r["peran"] in ("SUPPLIER", "DISTRIBUTOR") and rng.random() < 0.6:
        return "ANCHOR"
    return f"PEMILIK_PROYEK_{int(rng.integers(1, 400)):03d}"


def catalog_no(ref, name: str) -> int:
    hit = ref.catalog.loc[ref.catalog["Nama_Produk"] == name, "No"]
    return int(hit.iloc[0]) if len(hit) else -1


def facilities(ref, comp, rel, rng, cal) -> list:
    """Credit facilities of debtors at month 1: KUR for UMKM debtors; otherwise KMK for every
    debtor, KI for some, Supply Chain Financing for some partners of Bank anchors."""
    cfg = ref.cfg["wholesale"]
    d = comp[comp["status_debitur_awal"] == 1].set_index("company_id")
    anchors = set(comp.loc[comp["is_anchor"] & (comp["is_bank_customer"] == 1), "company_id"])
    partners = set(rel.loc[rel["from_id"].isin(anchors), "to_id"]) | set(rel.loc[rel["to_id"].isin(anchors), "from_id"])
    rows = []
    for cid, r in d.iterrows():
        if r["segmen_bank"] == "UMKM":
            rows.append(kur_row(ref, r, 0, cal, rng, cid))
            continue
        rows.append(facility_row(ref, r, "Kredit Modal Kerja", 112, 0, cal, rng, cid))
        if rng.random() < cfg["peluang_ki_jika_debitur"]:
            rows.append(facility_row(ref, r, "Kredit Investasi", 113, 0, cal, rng, cid))
        if cid in partners and not r["is_anchor"] and rng.random() < cfg["peluang_scf_jika_mitra_anchor_bank"]:
            rows.append(facility_row(ref, r, "Supply Chain Financing", 161, 0, cal, rng, cid))
    return rows


def facility_row(ref, r, name, no, month, cal, rng, cid=None) -> dict:
    """month 0 = started before the panel; otherwise started in that panel month."""
    cfg = ref.cfg["wholesale"]
    omzet = float(r["omzet_tahunan_rp"])
    share = cfg["plafon_ki_porsi_omzet"] if name == "Kredit Investasi" else cfg["plafon_kmk_porsi_omzet"]
    plafon = round(omzet * rng.uniform(*share), -6)
    p0 = pd.Timestamp(cal[1])
    if month == 0:
        start = p0 - pd.Timedelta(days=int(rng.integers(30, 1500)))
    else:
        start = month_date(cal, month, rng)
    years = int(rng.integers(3, 8)) if name == "Kredit Investasi" else 1
    end = start + pd.DateOffset(years=years)
    panel_end = pd.Timestamp(cal[ref.cfg["bulan"]]) + pd.offsets.MonthEnd(0)
    while name != "Kredit Investasi" and end <= panel_end:   # KMK and SCF roll over yearly
        end += pd.DateOffset(years=1)
    return {"company_id": cid if cid is not None else r.name, "produk": name, "no_katalog": no, "plafon_rp": plafon,
            "baki_debet_rp": round(plafon * rng.uniform(0.4, 0.95), -6), "tanggal_mulai": start.date().isoformat(),
            "jatuh_tempo": end.date().isoformat()}


def new_facility(ref, r, month, cal, rng) -> dict:
    """First facility of a new debtor: KUR for UMKM, else KI or KMK (ASUMSI split)."""
    if r["segmen_bank"] == "UMKM":
        return kur_row(ref, r, month, cal, rng)
    if rng.random() < ref.cfg["wholesale"]["porsi_ki_debitur_baru"]:
        return facility_row(ref, r, "Kredit Investasi", 113, month, cal, rng)
    return facility_row(ref, r, "Kredit Modal Kerja", 112, month, cal, rng)


def kur_row(ref, r, month, cal, rng, cid=None) -> dict:
    """KUR Mikro up to the micro limit, KUR Kecil above it (catalog no. 108, 109)."""
    cfg = ref.cfg["wholesale"]
    plafon = min(round(float(r["omzet_tahunan_rp"]) * rng.uniform(*cfg["plafon_kur_porsi_omzet"]), -6), cfg["batas_kur_kecil"])
    plafon = max(plafon, 5_000_000)
    name, no = ("KUR Mikro", 108) if plafon <= cfg["batas_kur_mikro"] else ("KUR Kecil", 109)
    start = (pd.Timestamp(cal[1]) - pd.Timedelta(days=int(rng.integers(30, 700)))) if month == 0 else month_date(cal, month, rng)
    end = start + pd.DateOffset(years=int(rng.integers(*cfg["tenor_kur_tahun"], endpoint=True)))
    return {"company_id": cid if cid is not None else r.name, "produk": name, "no_katalog": no, "plafon_rp": plafon,
            "baki_debet_rp": round(plafon * rng.uniform(0.3, 0.95), -5), "tanggal_mulai": start.date().isoformat(),
            "jatuh_tempo": end.date().isoformat()}


def balances(ref, comp, leak_month, rng, cal) -> pd.DataFrame:
    """Monthly average and month-end balance of each Bank company's accounts."""
    cfg, T = ref.cfg["wholesale"], ref.cfg["bulan"]
    c = comp[comp["is_bank_customer"] == 1].set_index("company_id")
    days = rng.uniform(*cfg["hari_kas"], len(c))
    base = c["omzet_tahunan_rp"].to_numpy() / 12 * days / 30
    lm = leak_month.reindex(c.index).to_numpy()
    out = []
    for t in range(1, T + 1):
        avg = base * np.exp(rng.normal(0, cfg["noise_saldo_sd_log"], len(c)))
        avg = np.where(t >= np.nan_to_num(lm, nan=np.inf), avg * cfg["leakage_pengali_saldo"], avg)
        end = avg * rng.uniform(*cfg["faktor_akhir_bulan"], len(c))
        out.append(pd.DataFrame({"bulan_ke": t, "bulan": cal[t], "company_id": c.index,
                                 "saldo_rata2_rp": np.round(avg, -3), "saldo_akhir_bulan_rp": np.round(end, -3)}))
    return pd.concat(out, ignore_index=True)


def rm_portfolio(cfg, comp) -> pd.DataFrame:
    p = comp[comp["rm_id"] != ""][["rm_id", "cabang", "company_id", "segmen_bank", "status_debitur_awal"]]
    return p.sort_values(["rm_id", "company_id"]).reset_index(drop=True)


def bisdev_leads(ref, comp, rel, transfers, rng, cal, last):
    """Bisdev Excel: non-nasabah counterparties of Bank anchors, big ones more likely; often just
    a name. The bank-side file has no company_id; the true match is kept for evaluation."""
    cfg, T = ref.cfg["wholesale"], ref.cfg["bulan"]
    c = comp.set_index("company_id")
    anchors = set(c.index[c["is_anchor"] & (c["is_bank_customer"] == 1)])
    w = transfers[(transfers["bulan_ke"] <= last)]
    links = pd.concat([w[w["from_id"].isin(anchors)].rename(columns={"from_id": "anchor", "to_id": "cp"}),
                       w[w["to_id"].isin(anchors)].rename(columns={"to_id": "anchor", "from_id": "cp"})])
    links = links[links["cp"].str.startswith("C") & links["cp"].map(c["is_bank_customer"]).eq(0)]
    tot = links.groupby(["cp", "anchor"])["total_nominal_rp"].sum().reset_index()
    tot = tot.sort_values("total_nominal_rp").drop_duplicates("cp", keep="last")
    n = min(cfg["lead_bisdev_jumlah"], len(tot))
    wgt = tot["total_nominal_rp"].to_numpy() ** 0.5
    pick = tot.iloc[rng.choice(len(tot), n, replace=False, p=wgt / wgt.sum())].reset_index(drop=True)
    start = pd.Timestamp(cal[1])
    gaps = rng.integers(*cfg["lead_bisdev_hari_update"], n, endpoint=True)
    upd = start + pd.to_timedelta(np.sort(np.cumsum(gaps) % ((pd.Timestamp(cal[T]) - start).days + 1)), unit="D")
    leads = pd.DataFrame({"lead_id": [f"L{i:05d}" for i in range(n)],
                          "nama_perusahaan": pick["cp"].map(c["nama_samaran"]).to_numpy(),
                          "anchor_terkait": pick["anchor"].map(c["nama_samaran"]).to_numpy(),
                          "sektor": pick["cp"].map(c["sektor"]).to_numpy(),
                          "provinsi": pick["cp"].map(c["provinsi"]).to_numpy(),
                          "tanggal_update": [d.date().isoformat() for d in upd]})
    for col, rate in cfg["lead_bisdev_kosong"].items():
        leads.loc[rng.random(n) < rate, col] = np.nan
    truth = pd.DataFrame({"lead_id": leads["lead_id"], "company_id": pick["cp"].to_numpy(), "anchor_id": pick["anchor"].to_numpy()})
    return leads, truth


def standardize(f: pd.DataFrame) -> pd.DataFrame:
    return (f - f.mean()) / f.std().replace(0, 1)


def draw_label(score: pd.Series, base_rate: float, noise_sd: float, rng) -> list:
    """Each candidate gets the event with probability expit(b0 + score + noise); b0 is set
    by bisection so the expected share equals the base rate."""
    if len(score) == 0:
        return []
    s = score.to_numpy() + rng.normal(0, noise_sd, len(score))
    lo, hi = -20.0, 20.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if expit(mid + s).mean() < base_rate else (lo, mid)
    hit = rng.random(len(s)) < expit((lo + hi) / 2 + s)
    return list(score.index[hit])


def month_date(cal, m, rng) -> pd.Timestamp:
    return pd.Timestamp(cal[int(m)]) + pd.Timedelta(days=int(rng.integers(0, 28)))
