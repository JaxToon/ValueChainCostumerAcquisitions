"""Cached readers of data/processed and outputs for the app (no Neo4j, no training)."""
import json

import numpy as np
import pandas as pd
import streamlit as st

from src.config import ROOT, path, settings

TYPES = ["perusahaan", "pedagang", "karyawan"]


@st.cache_data
def load(kind: str, name: str) -> pd.DataFrame:
    return pd.read_parquet(path("processed") / kind / f"{name}.parquet")


@st.cache_data
def report(name: str) -> pd.DataFrame:
    return pd.read_csv(path("outputs") / "model" / name)


@st.cache_data
def prospects() -> pd.DataFrame:
    """Acquisition test-window prospects with the champion score of their own type."""
    base = load("scores", "akuisisi_test")
    parts = []
    for t in TYPES:
        s = load("scores", f"akuisisi_{t}_test")[["entity_id", "skor", "model"]].rename(columns={"skor": "skor_tipe", "model": "model_tipe"})
        parts.append(s)
    per_type = pd.concat(parts)
    out = base.merge(per_type, on="entity_id", how="left")
    out["skor_tipe"] = out["skor_tipe"].fillna(out["skor"])
    out["peringkat_dalam_tipe"] = out.groupby("tipe_prospek")["skor_tipe"].rank(ascending=False, method="first").astype(int)
    comp = load("clean", "companies").set_index("company_id")
    out["nama"] = out["entity_id"].map(comp["nama_samaran"]).fillna(out["entity_id"])
    out["sektor_nama"] = sector_label(out["sektor"])
    return out


@st.cache_data
def portfolio() -> pd.DataFrame:
    pf = load("clean", "rm_portofolio")
    comp = load("clean", "companies").set_index("company_id")
    pf = pf.join(comp[["nama_samaran", "sektor", "provinsi", "is_anchor"]], on="company_id")
    pf["sektor"] = sector_label(pf["sektor"])        # full BPS name for display (A -> Pertanian, ...)
    pf["kanwil"] = pf["provinsi"].map(kanwil_map()["kanwil"])
    scores = {}
    for lab in ["cross_sell_wholesale", "leakage", "reaktivasi", "non_debitur_ke_debitur"]:
        s = load("scores", f"wholesale_{lab}_test").set_index("company_id")["skor"]
        pf[f"skor_{lab}"] = pf["company_id"].map(s)
    sig = load("signals", "sinyal_f19")
    sig = sig[sig["sinyal"] != "counterpart_berulang"]
    cnt = sig.groupby(["company_id", "sinyal"]).size().unstack(fill_value=0)
    pf = pf.join(cnt, on="company_id").fillna({c: 0 for c in cnt.columns})
    return pf


@st.cache_data
def leads_for(rm_id: str) -> pd.DataFrame:
    """Non-Bank counterparts of the RM's companies in the last 3 months, with their scores."""
    pf = portfolio()
    ids = set(pf.loc[pf["rm_id"] == rm_id, "company_id"])
    tx = load("clean", "transaksi_counterparty")
    T = settings()["bulan"]
    x = tx[tx["company_id"].isin(ids) & (tx["bulan_ke"] > T - 3) & (tx["counterparty_bank"] != "Bank")]
    agg = x.groupby(["counterparty_id"]).agg(nasabah_rm=("company_id", "first"), nominal_3bln_rp=("total_nominal_rp", "sum"),
                                              bulan_muncul=("bulan_ke", "nunique"), bank=("counterparty_bank", "last")).reset_index()
    pr = prospects().set_index("entity_id")
    agg = agg.join(pr[["skor_tipe", "peringkat_dalam_tipe", "tipe_prospek", "nama", "model_tipe"]], on="counterparty_id", how="inner")
    sig = load("signals", "sinyal_f19")
    new = set(sig.loc[sig["sinyal"] == "counterpart_baru", "counterparty_id"])
    moved = set(sig.loc[sig["sinyal"] == "counterparty_ganti_bank", "counterparty_id"])
    agg["sinyal"] = np.select([agg["counterparty_id"].isin(new), agg["counterparty_id"].isin(moved)], ["Counterpart baru", "Ganti bank"], "")
    comp = load("clean", "companies").set_index("company_id")
    agg["nasabah_rm_nama"] = agg["nasabah_rm"].map(comp["nama_samaran"])
    agg["sektor"] = sector_label(agg["counterparty_id"].map(comp["sektor"]))
    agg["provinsi"] = agg["counterparty_id"].map(comp["provinsi"])
    agg["sudah_bank"] = False                      # leads are counterparties at other banks
    agg = add_visit_contact(agg)
    return agg.sort_values("skor_tipe", ascending=False)


@st.cache_data
def anchor_showcase() -> str:
    """Grill me Q24: Corporate anchor with the most Commercial partners, the largest share of
    money to other banks, and at least one bank-switch signal and one reactivation candidate."""
    comp = load("clean", "companies")
    tx = load("clean", "transaksi_counterparty")
    seg = comp.set_index("company_id")["segmen_bank"]
    anchors = comp[comp["is_anchor"].astype(bool) & (comp["segmen_bank"] == "Corporate")]["company_id"]
    a = tx[tx["company_id"].isin(anchors) & (tx["counterparty_id"] != tx["company_id"])]
    stats = a.groupby("company_id").agg(mitra_commercial=("counterparty_id", lambda s: (s.map(seg) == "Commercial").sum()),
                                        porsi_bank_lain=("counterparty_bank", lambda s: (s != "Bank").mean()))
    sig = load("signals", "sinyal_f19")
    has_move = set(sig.loc[sig["sinyal"].isin(["pindah_bank", "counterparty_ganti_bank"]), "company_id"])
    partners = a.groupby("company_id")["counterparty_id"].apply(set)
    hist = load("clean", "riwayat_produk_wholesale")
    ended = set(hist.loc[(hist["jenis"] == "transaksi") & (hist["status"] == "TIDAK AKTIF"), "company_id"])
    ok = [c for c in stats.index if c in has_move and partners.get(c, set()) & ended]
    stats = stats.loc[ok] if ok else stats
    stats["rank"] = stats["mitra_commercial"].rank(pct=True) + stats["porsi_bank_lain"].rank(pct=True)
    return stats["rank"].idxmax()


REF = ROOT / "synthetic_generator" / "reference"


@st.cache_data
def sector_names() -> dict:
    """KBLI letter -> full sector name (BPS), e.g. A -> 'Pertanian, Kehutanan, dan Perikanan'."""
    return pd.read_csv(REF / "bps_pekerja_sektor_2025.csv").set_index("kode_kbli")["sektor"].to_dict()


def sector_label(codes: pd.Series) -> pd.Series:
    names = sector_names()
    return codes.astype(str).map(lambda c: names.get(c, c))


@st.cache_data
def kanwil_map() -> pd.DataFrame:
    """Province -> Bank regional office (kanwil.csv from the team + provinsi_kanwil.csv mapping)."""
    k = pd.read_csv(REF / "kanwil.csv")
    return pd.read_csv(REF / "provinsi_kanwil.csv").merge(k[["kanwil_id", "kanwil"]], on="kanwil_id", how="left").set_index("provinsi")


@st.cache_data
def partners(company_id: str, months: int = 6) -> pd.DataFrame:
    """Counterparties of one company over the last `months`: role (supplier = the company pays
    them, buyer = they pay the company), Bank or not, managing branch and RM for Bank customers,
    province and regional office for everyone, and monthly value and frequency.
    Transfers to the company's own accounts (same name) are excluded."""
    T = settings()["bulan"]
    tx = load("clean", "transaksi_counterparty")
    x = tx[(tx["company_id"] == company_id) & (tx["counterparty_id"] != company_id) & (tx["bulan_ke"] > T - months)
           & ~tx["kelas_nama_bank"].astype(str).str.startswith("NAMA_SAMA")]
    if x.empty:
        return pd.DataFrame()
    g = x.groupby("counterparty_id").agg(nama=("counterparty_nama", "last"), bank=("counterparty_bank", "last"),
                                         frekuensi=("jumlah_transaksi", "sum"), bulan_aktif=("bulan_ke", "nunique"))
    by_dir = x.pivot_table(index="counterparty_id", columns="arah", values="total_nominal_rp", aggfunc="sum", fill_value=0)
    g["nominal_keluar"] = by_dir.get("KELUAR", 0)
    g["nominal_masuk"] = by_dir.get("MASUK", 0)
    g = g.fillna({"nominal_keluar": 0, "nominal_masuk": 0})
    g["peran"] = np.select([(g["nominal_keluar"] > 0) & (g["nominal_masuk"] > 0), g["nominal_keluar"] > 0],
                           ["Supplier dan buyer", "Supplier"], "Buyer")
    g["nominal_per_bulan"] = (g["nominal_keluar"] + g["nominal_masuk"]) / months
    g["frekuensi_per_bulan"] = g["frekuensi"] / months
    comp = load("clean", "companies").set_index("company_id")
    g = g.join(comp[["nama_samaran", "sektor", "provinsi", "cabang", "rm_id", "is_bank_customer"]])
    g["sudah_bank"] = g["is_bank_customer"].fillna(0).astype(bool) | g["bank"].eq("Bank")
    g["nama"] = g["nama_samaran"].fillna(g["nama"])    # clean name; raw transfer names are dirty (PT MITRA 2423)
    g = g.drop(columns=["nama_samaran", "is_bank_customer"])
    g["sektor"] = sector_label(g["sektor"])
    g = add_visit_contact(g)
    return g.reset_index().rename(columns={"counterparty_id": "mitra_id"}).sort_values("nominal_per_bulan", ascending=False)


@st.cache_data
def rms_by_branch() -> dict:
    pf = load("clean", "rm_portofolio")
    return pf.groupby("cabang")["rm_id"].apply(lambda s: sorted(s.unique())).to_dict()


def add_visit_contact(df: pd.DataFrame) -> pd.DataFrame:
    """Where an entity is and whom the RM can contact before visiting it.
    kc_lokasi: Bank branch in the entity's area (synthetic data has one KC per province).
    kontak_visit: Bank customer -> its managing RM and branch; prospect -> the RMs at the branch
    in its area, or the regional office when that branch has no RM."""
    df = df.copy()
    df["kc_lokasi"] = "KC " + df["provinsi"].astype(str)
    df["kanwil"] = df["provinsi"].map(kanwil_map()["kanwil"])
    rms = rms_by_branch()

    def contact(r):
        if r.get("sudah_bank") and isinstance(r.get("rm_id"), str):
            return f"RM {r['rm_id']} ({r['cabang']}, pengelola)"
        local = rms.get(r["kc_lokasi"])
        if local:
            more = f" +{len(local) - 3} lainnya" if len(local) > 3 else ""
            return f"RM {', '.join(local[:3])}{more} ({r['kc_lokasi']})"
        return f"{r['kanwil']} (belum ada RM di {r['kc_lokasi']})" if isinstance(r["kanwil"], str) else "–"

    df["kontak_visit"] = df.apply(contact, axis=1)
    cabang = df["cabang"] if "cabang" in df else pd.Series(pd.NA, index=df.index)
    df["kc_kelolaan"] = np.where(df["sudah_bank"], cabang.fillna("–"), "belum nasabah")
    return df


@st.cache_data
def anchor_benchmark(months: int = 6) -> dict:
    """Median over all anchors (last `months`): share of partners that already bank at Bank and
    close loop (share of value that stays inside Bank). Baseline for the ecosystem cards."""
    T = settings()["bulan"]
    tx, comp = load("clean", "transaksi_counterparty"), load("clean", "companies")
    anchors = set(comp.loc[comp["is_anchor"].astype(bool), "company_id"])
    bank_comp = set(comp.loc[comp["is_bank_customer"].fillna(0).astype(bool), "company_id"])
    x = tx[tx["company_id"].isin(anchors) & (tx["counterparty_id"] != tx["company_id"]) & (tx["bulan_ke"] > T - months)
           & ~tx["kelas_nama_bank"].astype(str).str.startswith("NAMA_SAMA")].copy()
    x["di_bank"] = x["counterparty_bank"].eq("Bank")
    x["mitra_bank"] = x["di_bank"] | x["counterparty_id"].isin(bank_comp)
    share = x.groupby(["company_id", "counterparty_id"])["mitra_bank"].max().groupby("company_id").mean()
    loop = x.assign(v=x["total_nominal_rp"] * x["di_bank"]).groupby("company_id")[["v", "total_nominal_rp"]].sum()
    return {"porsi_mitra_bank": float(share.median()), "close_loop": float((loop["v"] / loop["total_nominal_rp"]).median()),
            "jumlah_anchor": int(len(share))}


@st.cache_data
def monthly_flows(company_id: str, months: int = 6) -> pd.DataFrame:
    """Per month: value per channel and close loop = share of value with counterparties that bank
    at Bank (money that stays inside Bank). Own-account transfers are excluded."""
    T = settings()["bulan"]
    tx = load("clean", "transaksi_counterparty")
    x = tx[(tx["company_id"] == company_id) & (tx["counterparty_id"] != company_id) & (tx["bulan_ke"] > T - months)
           & ~tx["kelas_nama_bank"].astype(str).str.startswith("NAMA_SAMA")].copy()
    x["di_bank"] = x["counterparty_bank"].eq("Bank")
    by_ch = x.pivot_table(index="bulan", columns="channel", values="total_nominal_rp", aggfunc="sum", fill_value=0)
    loop = x.groupby("bulan").apply(lambda d: d.loc[d["di_bank"], "total_nominal_rp"].sum() / max(d["total_nominal_rp"].sum(), 1),
                                    include_groups=False).rename("close_loop")
    cnt = x.groupby("bulan")["jumlah_transaksi"].sum().rename("jumlah_transaksi")
    return by_ch.join(loop).join(cnt).reset_index()


@st.cache_data
def products_used(company_id: str) -> pd.DataFrame:
    h = load("clean", "riwayat_produk_wholesale")
    return h[h["company_id"] == company_id][["produk", "status", "tanggal_mulai", "tanggal_selesai", "konteks"]]


@st.cache_data
def default_rm() -> str:
    """Commercial RM with the most partners of the showcase anchor (demo wholesale account)."""
    pf = portfolio()
    tx = load("clean", "transaksi_counterparty")
    partners = set(tx.loc[tx["counterparty_id"] == anchor_showcase(), "company_id"])
    comm = pf[pf["segmen_bank"] == "Commercial"]
    return comm.assign(m=comm["company_id"].isin(partners)).groupby("rm_id")["m"].sum().idxmax()


PELUANG_6_BULAN = (
    "**Peluang 6 bulan** = perkiraan kemungkinan (0–100%) calon ini **membuka rekening atau produk pertamanya di Bank "
    "dalam 6 bulan ke depan**. Angkanya terkalibrasi: dari 100 calon dengan peluang 20%, sekitar 20 benar-benar menjadi nasabah.  \n"
    "Dihitung dari data transaksi 5 bulan terakhir yang terlihat bank: **berapa mitra transaksinya yang sudah nasabah Bank**, "
    "**berapa rekan sesama mitra anchor yang sudah Bank**, **nilai dan rutinitas transaksi dengan nasabah Bank**, **tren nilai transaksi**, "
    "**mitra yang baru bergabung ke Bank**, **posisinya di jaringan anchor**, dan **sektor usaha**. "
    "Tidak memakai data pribadi di luar transaksi (rahasia bank).")


def type_of(df: pd.DataFrame) -> pd.Series:
    return np.select([df["tipe_perusahaan"] == 1, df["peran_pedagang"] == 1, df["peran_karyawan"] == 1],
                     ["perusahaan", "pedagang", "karyawan"], "lainnya")


@st.cache_data
def base_rate() -> dict:
    """Historical 6-month conversion per prospect type and per (type, sector), from the
    validation window (the window before the one shown), used as the baseline in cards."""
    f = pd.read_parquet(path("processed") / "features" / "akuisisi.parquet",
                        columns=["jendela_k", "label", "sektor", "tipe_perusahaan", "peran_pedagang", "peran_karyawan"])
    f = f[f["jendela_k"] == 1].assign(tipe_prospek=lambda d: type_of(d), sektor=lambda d: d["sektor"].astype(str))
    return {"tipe": f.groupby("tipe_prospek")["label"].mean().to_dict(),
            "sektor": f.groupby(["tipe_prospek", "sektor"])["label"].mean().to_dict()}


@st.cache_resource
def _acq_context():
    """Transfers the acquisition model saw for the shown window (lookback months up to the last
    feature month) and who was a Bank customer then, to turn SHAP reasons into counts."""
    w = settings()["windows"]
    last, lb, k = w["akuisisi"][-1][0], w["lookback_bulan"], len(w["akuisisi"])
    tr, acq = load("clean", "transfers"), load("clean", "acquisitions")
    persons, comp = load("clean", "persons"), load("clean", "companies")
    joined = acq[(acq["jendela"] > 0) & (acq["jendela"] < k)]
    own_cust = (set(persons.loc[persons["is_bank_customer"] == 1, "person_id"]) | set(comp.loc[comp["is_bank_customer"] == 1, "company_id"])
           | set(joined["entity_id"]))
    recent = set(joined.loc[joined["bulan_jadi_nasabah"] > last - 3, "entity_id"])
    x = tr[(tr["bulan_ke"] <= last) & (tr["bulan_ke"] > last - lb)][["from_id", "to_id", "bulan_ke", "total_nominal_rp", "jumlah_transaksi"]]
    e = pd.concat([x.rename(columns={"from_id": "src", "to_id": "dst"}), x.rename(columns={"to_id": "src", "from_id": "dst"})], ignore_index=True)
    return e.groupby("src"), own_cust, recent, last, lb


def _rp(x) -> str:
    from app.components.ui import rupiah
    return rupiah(x)


def reason_detail(entity_id: str, feature: str, value: float, tipe: str, peers: pd.DataFrame) -> str:
    """One SHAP reason in business terms, with the counts behind it (how many partners, how many
    of them already bank at Bank, Rp, months) and a comparison with other prospects of the type."""
    from app.components.ui import pct
    groups, own_cust, recent, last, lb = _acq_context()
    me = groups.get_group(entity_id) if entity_id in groups.groups else pd.DataFrame(columns=["dst", "bulan_ke", "total_nominal_rp", "jumlah_transaksi"])
    nb = set(me["dst"])
    nb_bank = nb & own_cust
    tot = float(me["total_nominal_rp"].sum())
    with_bank = me[me["dst"].isin(own_cust)]
    num = lambda x: f"{x:,.0f}".replace(",", ".")                                      # noqa: E731

    def rank(col: str) -> str:
        if col not in peers:
            return "-"
        share = (peers[col] < value).mean()
        return "hampir semua (99%)" if share > 0.99 else pct(share, 0)

    med = lambda col: peers[col].median() if col in peers else float("nan")           # noqa: E731
    if feature == "porsi_bank_dua_langkah":
        two = set()
        for n in nb:
            if n in groups.groups:
                two |= set(groups.get_group(n)["dst"])
        two -= {entity_id}
        n2 = len(two & own_cust)
        return (f"**Banyak rekan sesama mitra yang sudah Bank**: lewat {len(nb)} mitranya, calon ini terhubung ke {num(len(two))} rekan "
                f"(sesama pemasok/pembeli anchor, rekan kerja); **{num(n2)} di antaranya ({pct(n2 / max(len(two), 1), 0)}) sudah nasabah Bank** "
                f"· calon lain di tipe ini rata-rata {pct(med('porsi_bank_dua_langkah'), 0)}")
    if feature == "porsi_tetangga_bank":
        return (f"**Mitra transaksinya sudah Bank**: {len(nb_bank)} dari {len(nb)} mitra langsung ({pct(len(nb_bank) / max(len(nb), 1), 0)}) "
                f"sudah nasabah Bank · rata-rata calon lain {pct(med('porsi_tetangga_bank'), 0)}")
    if feature == "log_nominal_dengan_bank":
        return (f"**Nilai transaksi dengan nasabah Bank besar**: {_rp(with_bank['total_nominal_rp'].sum())} dalam {lb} bulan "
                f"({pct(with_bank['total_nominal_rp'].sum() / max(tot, 1), 0)} dari total {_rp(tot)}), dengan {len(nb_bank)} mitra Bank "
                f"· lebih besar dari {rank('log_nominal_dengan_bank')} calon lain")
    if feature == "bulan_aktif_dengan_bank":
        return (f"**Rutin bertransaksi dengan nasabah Bank**: {with_bank['bulan_ke'].nunique()} dari {lb} bulan terakhir, "
                f"dengan {len(nb_bank)} mitra Bank")
    if feature == "tetangga_baru_bergabung":
        n = len(nb & recent)
        return f"**Mitranya baru bergabung ke Bank**: {n} mitra langsungnya menjadi nasabah Bank dalam 3 bulan terakhir"
    if feature == "log_nominal_total":
        return (f"**Volume transaksi besar**: {_rp(tot)} dalam {lb} bulan (sekitar {_rp(tot / lb)} per bulan) "
                f"· lebih besar dari {rank('log_nominal_total')} calon lain")
    if feature == "log_jumlah_transaksi":
        return (f"**Sering bertransaksi**: {num(me['jumlah_transaksi'].sum())} transaksi dalam {lb} bulan "
                f"· lebih sering dari {rank('log_jumlah_transaksi')} calon lain")
    if feature == "bulan_aktif":
        return f"**Aktif rutin**: bertransaksi di {me['bulan_ke'].nunique()} dari {lb} bulan terakhir"
    if feature == "n_tetangga":
        return (f"**Banyak mitra transaksi**: {len(nb)} mitra, {len(nb_bank)} di antaranya sudah Bank "
                f"· lebih banyak dari {rank('n_tetangga')} calon lain")
    if feature == "tren_nominal_3bln":
        now = me.loc[me["bulan_ke"] > last - 3, "total_nominal_rp"].sum() / 3
        before_m = me.loc[me["bulan_ke"] <= last - 3, "bulan_ke"].nunique() or 1
        before = me.loc[me["bulan_ke"] <= last - 3, "total_nominal_rp"].sum() / before_m
        arah = "naik" if now >= before else "turun"
        return (f"**Transaksi sedang {arah}**: rata-rata {_rp(now)} per bulan dalam 3 bulan terakhir, "
                f"dibanding {_rp(before)} per bulan sebelumnya ({pct(now / before - 1, 0) if before else 'baru mulai'})")
    if feature == "pagerank":
        return (f"**Posisinya sentral di jaringan anchor**: banyak alur pembayaran melewatinya; lebih sentral dari "
                f"{rank('pagerank')} calon lain di tipe ini ({len(nb)} mitra langsung)")
    if feature == "porsi_bank_komunitas":
        return (f"**Berada di kelompok ekosistem yang banyak nasabah Bank-nya**: {pct(value, 0)} akun di kelompok transaksinya "
                f"sudah Bank · rata-rata calon lain {pct(med('porsi_bank_komunitas'), 0)}")
    if feature in ("mirip_nasabah_bank", "mirip_yang_baru_bergabung"):
        return f"**Pola transaksinya mirip nasabah Bank**: lebih mirip dari {rank(feature)} calon lain di tipe ini"
    if feature.startswith("sektor_"):
        code = feature.removeprefix("sektor_")
        name = sector_names().get(code, code)
        br = base_rate()
        rate, avg = br["sektor"].get((tipe, code)), br["tipe"].get(tipe)
        hist = (f"{pct(rate, 1)} calon di sektor {name} menjadi nasabah dalam 6 bulan (periode sebelumnya), "
                f"rata-rata semua sektor {pct(avg, 1)}") if rate is not None else ""
        lead = "Sektor tempat kerja" if tipe == "karyawan" else "Sektor usaha"
        if value >= 0.5:
            return f"**{lead}: {name}**: {hist}"
        return f"**{lead} bukan {name}** (sektor dengan konversi lebih rendah): {hist}"
    from src.genai import prompts
    return prompts.label(feature)


def log_rows(limit=500):
    from src.guardrails import audit_log
    df = audit_log.read(limit)
    for c in ["guardrail_input", "guardrail_output"]:
        df[c] = df[c].fillna("{}").map(lambda s: json.loads(s) if s else {})
    return df
