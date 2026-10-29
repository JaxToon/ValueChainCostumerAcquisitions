"""Guardrail layer 3 (output): every recommended product must exist in the catalog, be
allowed for this customer (catalog + regulator rules), carry the catalog source, and the
external pitch must not leak other customers' data (rahasia bank) and must carry the OJK
footer (POJK 22/2023 Pasal 35)."""
import re
from dataclasses import dataclass, field

import pandas as pd

from src.config import ROOT
from src.genai.rag import product
from src.guardrails.input_guard import MASKS

OJK_FOOTER = "Bank berizin dan diawasi oleh Otoritas Jasa Keuangan."
# Lower and upper bound (Rp/month) of each KYC income range.
INCOME_RANGE = {"< 500 rb": (0, 5e5), "500 rb - 1,5 jt": (5e5, 1.5e6), "1,5 - 2,5 jt": (1.5e6, 2.5e6),
                "2,5 - 3,5 jt": (2.5e6, 3.5e6), "> 3,5 jt": (3.5e6, float("inf")), "Tidak ada penghasilan sendiri": (0, 0)}
INVESTMENT = {"Reksa Dana (agen penjual)", "Bonds"}
CHILD_ACCOUNT = {"Tabungan Plus Anak"}
LEAK = [re.compile(r"\b(PT|CV)\.?\s+(Anchor|Mitra)\s+\d+", re.I), re.compile(r"Rp\s?[\d.,]+\s?(juta|miliar|triliun|jt|M|T)?", re.I)]


@dataclass
class OutputCheck:
    approved: list[str] = field(default_factory=list)
    blocked: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    pitch: str = ""


def rules() -> pd.DataFrame:
    return pd.read_csv(ROOT / "synthetic_generator" / "reference" / "produk_model.csv", keep_default_na=False).set_index("produk")


def eligible(name: str, who: dict) -> tuple[bool, str]:
    """who: usia, pekerjaan, kisaran_pendapatan (person) or segmen_bank, umur_usaha (company)."""
    cat = product(name)
    if cat is None:
        return False, "produk tidak ada di katalog Bank"
    if not cat.get("boleh_direkomendasikan", True) and not (cat.get("hanya_corporate_besar") and who.get("segmen_bank") == "Corporate"):
        return False, "produk tidak termasuk daftar yang boleh direkomendasikan (anak usaha/kanal digital/API)"
    if "usia" in who and who["usia"] is not None:
        age = float(who["usia"])
        if age < 17 and name not in CHILD_ACCOUNT:
            return False, "nasabah di bawah 17 tahun hanya boleh rekening anak"
        r = rules()
        if name in r.index:
            row = r.loc[name]
            lo, hi = INCOME_RANGE.get(str(who.get("kisaran_pendapatan")), (None, None))
            if not (int(row["umur_min"]) <= age <= int(row["umur_max"])):
                return False, f"usia di luar syarat produk ({row['umur_min']}-{row['umur_max']} tahun)"
            if float(row["pendapatan_min"]) > 0 and (hi is None or hi < float(row["pendapatan_min"])):
                return False, f"penghasilan di bawah syarat minimal Rp{float(row['pendapatan_min']):,.0f}".replace(",", ".")
            if row["pekerjaan_syarat"] != "semua" and who.get("pekerjaan") not in row["pekerjaan_syarat"].split(";"):
                return False, "pekerjaan tidak sesuai syarat produk"
    if name.startswith("KUR") and who.get("segmen_bank") not in (None, "UMKM"):
        return False, "KUR hanya untuk UMKM"
    if name in {"Kredit Modal Kerja", "Kredit Investasi"} and who.get("umur_usaha") is not None and who["umur_usaha"] < 3:
        return False, "KMK/KI butuh usaha berjalan minimal 3 tahun"
    return True, ""


# Promised or guaranteed returns in a customer pitch (POJK 22/2023 on consumer protection: no misleading
# offers). Sentences that match are removed from the external pitch.
PROMISE = re.compile(r"imbal(an)? hasil|pasti (untung|naik|cuan)|keuntungan (pasti|terjamin|tetap)|dijamin (untung|naik)|"
                     r"bebas risiko|tanpa risiko|return (pasti|tinggi)|bunga (tinggi|terbaik)", re.I)


def drop_promises(text: str) -> tuple[str, int]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    keep = [s for s in parts if not PROMISE.search(s)]
    return " ".join(keep), len(parts) - len(keep)


def leaks(text: str) -> list[str]:
    found = [p.pattern for p, _ in MASKS if p.search(text)]
    found += [p.pattern for p in LEAK if p.search(text)]
    return found


def check(products: list[str], who: dict, pitch: str = "", sources: list[str] | None = None) -> OutputCheck:
    out = OutputCheck()
    for name in products:
        ok, why = eligible(name, who)
        if ok:
            out.approved.append(name)
        else:
            out.blocked.append({"produk": name, "alasan": why})
        cat = product(name)
        if cat and sources is not None and cat.get("URL_Sumber") not in sources:
            out.notes.append(f"sumber untuk {name} ditambahkan dari katalog")
        if name in INVESTMENT:
            out.notes.append(f"{name}: wajib cek profil risiko dan SID sebelum ditawarkan")
        if cat and str(cat.get("Perlu_Verifikasi")) in ("Ya", "Sebagian"):
            out.notes.append(f"{name}: cek ketentuan terbaru (katalog menandai Perlu_Verifikasi)")
    if pitch:
        bad = leaks(pitch)
        clean = pitch
        for p, token in MASKS:
            clean = p.sub(token, clean)
        for p in LEAK:
            clean = p.sub("[DISAMARKAN]", clean)
        if bad:
            out.notes.append("pitch eksternal memuat data yang disamarkan (nama anchor, nominal, atau ID)")
        body = clean.replace(OJK_FOOTER, "").rstrip()
        body, n = drop_promises(body)
        if n:
            out.notes.append(f"{n} kalimat janji imbal hasil dihapus dari pitch (POJK 22/2023)")
            clean = body
        if OJK_FOOTER not in clean:
            clean = clean.rstrip() + "\n\n" + OJK_FOOTER
        out.pitch = clean
    return out
