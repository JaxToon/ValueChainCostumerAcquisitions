"""The six read-only tools of the RM Copilot agent (F17), reading only data/processed.
No tool sends messages, opens accounts or contacts anyone."""
from functools import lru_cache

import numpy as np
import pandas as pd

from src.config import path, settings
from src.genai import rag
from src.guardrails import output_guard

# F20: business need -> catalog products (Guideline section 14, interview 11.3; to be checked by RM/PS).
NEED_PRODUCTS = {
    "penempatan_dana": ["Bank Giro (Non Perorangan)", "Bank Deposito Non Perorangan"],
    "banyak_pembayar": ["Bank Virtual Account Kredit (e-Collection)", "CIB Receivables"],
    "banyak_penerima": ["Bank Virtual Account Debit", "CIB Cash"],
    "trade": ["Impor (L/C, pembiayaan)", "SKBDN", "Garansi Bank"],
    "rantai_pasok": ["Supply Chain Financing", "CIB Supply Chain"],
    "karyawan": ["Payroll Korporasi"],
    "umkm": ["QRIS Bank", "KUR Mikro"],
}
STAKEHOLDER = {"Kredit Modal Kerja": "RM Credit", "Kredit Investasi": "RM Credit", "Supply Chain Financing": "RM Credit",
               "KUR Mikro": "RM Credit", "KUR Kecil": "RM Credit", "Bank Giro (Non Perorangan)": "Branch Manager",
               "Bank Deposito Non Perorangan": "Branch Manager", "Garansi Bank": "Product Specialist",
               "Impor (L/C, pembiayaan)": "Product Specialist", "Ekspor (L/C, negosiasi, pembiayaan)": "Product Specialist",
               "SKBDN": "Product Specialist", "SBLC": "Product Specialist"}


def rp(x) -> str:
    """Readable rupiah for the model, so drafts say 'Rp279,5 miliar' instead of a raw float."""
    if x is None or pd.isna(x):
        return "-"
    a = abs(float(x))
    for div, unit in [(1e12, "triliun"), (1e9, "miliar"), (1e6, "juta")]:
        if a >= div:
            return f"Rp{x / div:,.1f} {unit}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"Rp{x:,.0f}".replace(",", ".")


@lru_cache
def sector_names() -> dict:
    from src.config import ROOT
    return pd.read_csv(ROOT / "synthetic_generator" / "reference" / "bps_pekerja_sektor_2025.csv").set_index("kode_kbli")["sektor"].to_dict()


@lru_cache
def load(kind: str, name: str) -> pd.DataFrame:
    return pd.read_parquet(path("processed") / kind / f"{name}.parquet")


def entity_type(entity_id: str) -> str:
    comp = load("clean", "companies").set_index("company_id")
    if entity_id in comp.index:
        return "nasabah_korporasi" if comp.at[entity_id, "is_bank_customer"] == 1 else "prospek_perusahaan"
    nas = load("clean", "nasabah")
    return "nasabah_perorangan" if entity_id in set(nas["person_id"]) else "prospek_perorangan"


def ambil_profil(entity_id: str) -> dict:
    t = entity_type(entity_id)
    if t.startswith("nasabah_korporasi") or t == "prospek_perusahaan":
        c = load("clean", "companies").set_index("company_id").loc[entity_id]
        prof = {"tipe": t, "sektor": sector_names().get(str(c["sektor"]), c["sektor"]), "provinsi": c["provinsi"], "segmen": c.get("segmen_bank"),
                "tahun_berdiri": c.get("tahun_berdiri"), "anchor": bool(c["is_anchor"])}
        if t == "nasabah_korporasi":
            h = load("clean", "riwayat_produk_wholesale")
            h = h[h["company_id"] == entity_id]
            prof["produk"] = h[["produk", "status", "tanggal_mulai", "tanggal_selesai", "konteks", "nilai_proyek_rp"]].to_dict("records")
            f = load("clean", "fasilitas_pembiayaan")
            prof["fasilitas"] = f[f["company_id"] == entity_id][["produk", "plafon_rp", "jatuh_tempo"]].to_dict("records")
            s = load("clean", "saldo")
            s = s[s["company_id"] == entity_id].sort_values("bulan_ke").tail(3)
            prof["saldo_rata2_3bln"] = rp(s["saldo_rata2_rp"].mean()) if len(s) else None
            sig = load("signals", "sinyal_f19")
            sig = sig[(sig["company_id"] == entity_id) & (sig["sinyal"] != "counterpart_berulang")]
            prof["sinyal_f19"] = sig.groupby("sinyal").size().to_dict()
            tx = load("clean", "transaksi_counterparty")
            x = tx[(tx["company_id"] == entity_id) & (tx["bulan_ke"] > settings()["bulan"] - 3)]
            prof["transaksi_3bln"] = {"masuk": rp(x.loc[x["arah"] == "MASUK", "total_nominal_rp"].sum()),
                                      "keluar": rp(x.loc[x["arah"] == "KELUAR", "total_nominal_rp"].sum()),
                                      "jumlah_counterparty": int(x["counterparty_id"].nunique()),
                                      "porsi_ke_bank_lain": f"{(x['counterparty_bank'] != 'Bank').mean():.0%}" if len(x) else "0%"}
        return prof
    nas = load("clean", "nasabah").set_index("person_id")
    if t == "nasabah_perorangan":
        n = nas.loc[entity_id]
        panel = load("clean", "nasabah_bulanan")
        last = panel[panel["person_id"] == entity_id].sort_values("bulan_ke").tail(1)
        held = [c.removeprefix("prod_") for c in last.columns if c.startswith("prod_") and last[c].iloc[0] == 1] if len(last) else []
        return {"tipe": t, "usia": float(last["usia"].iloc[0]) if len(last) else n["usia_bulan1"], "pekerjaan": n["pekerjaan"],
                "kisaran_pendapatan": n["kisaran_pendapatan"], "provinsi": n["provinsi"], "produk_dipegang": held}
    emp = load("clean", "employment")
    role = emp.loc[emp["person_id"] == entity_id, "peran"]
    return {"tipe": t, "peran": role.iloc[0] if len(role) else None}


def skor_produk(entity_id: str, k: int = 3) -> list[dict]:
    t = entity_type(entity_id)
    if t == "nasabah_perorangan":
        s = load("scores", "nbo_test")
        s = s[s["person_id"] == entity_id].sort_values("skor", ascending=False).head(k)
        ex = load("explain", "nbo_lokal")
        nb = load("explain", "nbo_tetangga")
        rows = []
        for _, r in s.iterrows():
            e = ex[(ex["person_id"] == entity_id) & (ex["produk"] == r["produk"])]
            n = nb[(nb["person_id"] == entity_id) & (nb["produk"] == r["produk"])]
            # Similar customers are cited only when they hold the product clearly more often than
            # average (lift >= 1.5, about 9% of recommendations); otherwise SHAP reasons carry it.
            if len(n) and not (n["lift_tetangga"].iloc[0] >= 1.5 if "lift_tetangga" in n else True):
                n = n.iloc[0:0]
            rows.append({"produk": r["produk"], "skor": round(float(r["skor"]), 4),
                         "alasan": [e[f"alasan_{i}"].iloc[0] for i in range(1, 4)] if len(e) else [],
                         "porsi_nasabah_mirip_memegang": round(float(n["porsi_tetangga_memegang"].iloc[0]), 3) if len(n) else None,
                         "porsi_semua_nasabah": round(float(n["porsi_semua_nasabah"].iloc[0]), 3) if "porsi_semua_nasabah" in n and len(n) else None})
        return rows
    if t in ("prospek_perusahaan", "prospek_perorangan"):
        s = load("scores", "akuisisi_test")
        r = s[s["entity_id"] == entity_id]
        ex = load("explain", "akuisisi_lokal")
        e = ex[ex["entity_id"] == entity_id]
        first = "Bank Giro (Non Perorangan)" if t == "prospek_perusahaan" else "Tabungan Plus Bisnis"
        if t == "prospek_perorangan" and len(r) and r["peran_karyawan"].iloc[0] == 1:
            first = "Tabungan Plus"
        return [{"produk": first, "skor": round(float(r["skor"].iloc[0]), 4) if len(r) else None,
                 "peringkat_dalam_tipe": int(r["peringkat_dalam_tipe"].iloc[0]) if len(r) else None,
                 "alasan": [e[f"alasan_{i}"].iloc[0] for i in range(1, 4)] if len(e) else []}]
    # Bank company: wholesale cross-sell score + need-based products (F20).
    w = load("features", "wholesale")
    f = w[(w["company_id"] == entity_id)].sort_values("jendela_k").tail(1)
    if f.empty:
        return []
    f = f.iloc[0]
    needs = []
    if f["log_saldo_rata2"] >= np.log1p(1e9):
        needs.append("penempatan_dana")
    if f["n_pembayar"] >= 5:
        needs.append("banyak_pembayar")
    if f["n_penerima"] >= 5:
        needs.append("banyak_penerima")
    if f["sektor"] in ("C", "G", "F"):
        needs.append("trade")
    if f["transaksi_dengan_anchor_bank"] > 0:
        needs.append("rantai_pasok")
    if f["segmen_bank"] == "UMKM":
        needs = ["umkm"] + needs
    held = {p["produk"] for p in ambil_profil(entity_id).get("produk", [])}
    s = load("scores", "wholesale_cross_sell_wholesale_test")
    sc = s.loc[s["company_id"] == entity_id, "skor"]
    out = []
    for need in needs:
        for p in NEED_PRODUCTS[need]:
            if p not in held and p not in [o["produk"] for o in out]:
                out.append({"produk": p, "kebutuhan": need, "skor_cross_sell": round(float(sc.iloc[0]), 4) if len(sc) else None,
                            "stakeholder": STAKEHOLDER.get(p, "RM")})
    return out[:k + 2]


def cek_kelayakan(entity_id: str, produk: str | list[str]) -> dict | list[dict]:
    """One product, or a list of products in a single step (saves agent steps)."""
    if isinstance(produk, list):
        return [cek_kelayakan(entity_id, p) for p in produk]
    prof = ambil_profil(entity_id)
    who = {"usia": prof.get("usia"), "pekerjaan": prof.get("pekerjaan"), "kisaran_pendapatan": prof.get("kisaran_pendapatan"),
           "segmen_bank": prof.get("segmen")}
    if prof.get("tahun_berdiri") is not None and not pd.isna(prof.get("tahun_berdiri")):
        who["umur_usaha"] = 2026 - float(prof["tahun_berdiri"])
    ok, why = output_guard.eligible(produk, {k: v for k, v in who.items() if v is not None})
    return {"produk": produk, "layak": ok, "alasan": why}


def cari_katalog(query: str | list[str], k: int = 3) -> list[dict]:
    """A free-text query, or a list of product names (top hit of each) in a single step."""
    if isinstance(query, list):
        return [r for q in query for r in cari_katalog(q, 1)]
    exact = rag.product(query)  # a product name: its own row, not a TF-IDF neighbour such as the corporate variant
    if exact is not None and k == 1:
        return [{c: exact[c] for c in rag.search(query, 1).drop(columns="skor_cari").columns}]
    return rag.search(query, k).drop(columns="skor_cari").to_dict("records")


def cek_compliance(teks: str) -> dict:
    return {"temuan": output_guard.leaks(teks), "footer_ojk": output_guard.OJK_FOOTER in teks}


def susun_draft(**bagian) -> dict:
    """Assemble the F22 preparation pack; the agent passes the sections it wrote."""
    return {k: v for k, v in bagian.items() if v is not None}


TOOLS = {"ambil_profil": ambil_profil, "skor_produk": skor_produk, "cek_kelayakan": cek_kelayakan,
         "cari_katalog": cari_katalog, "cek_compliance": cek_compliance, "susun_draft": susun_draft}
