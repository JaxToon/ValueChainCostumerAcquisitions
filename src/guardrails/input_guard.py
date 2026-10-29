"""Guardrail layer 1 (input): prompt-injection patterns, topic restriction, and masking of
IDs, account numbers, phone numbers and emails before anything reaches the LLM."""
import re
from dataclasses import dataclass, field

INJECTION = [r"abaikan (semua )?(instruksi|aturan|perintah)", r"ignore (all |previous )?(instructions|rules)",
             r"system prompt", r"kamu sekarang (adalah|menjadi)", r"you are now", r"jailbreak", r"\bDAN\b",
             r"tampilkan (semua )?data (nasabah|pribadi)", r"bocorkan", r"reveal", r"developer mode",
             r"lupakan (aturan|instruksi)", r"bypass"]
# Requests for other parties' contacts or personal data (PRD section 18: no contact enrichment).
DATA_REQUEST = [r"(kirim|minta|berikan|kasih|daftar|list|export|ekspor|unduh)\s.*"
                r"(nomor (telepon|hp|wa)|no\.? ?(hp|telp|wa)|kontak|alamat|email|nik|ktp|nomor rekening)",
                # balances or transactions of a specific or another customer (rahasia bank)
                r"(saldo|mutasi|transaksi)\w*\b.*\b(nasabah|rekening|[cpq]\d{6,7})", r"(tampilkan|lihat|cek|berapa)\s.*saldo",
                r"nasabah lain",
                r"(nama|daftar|siapa)\W.*(buyer|supplier|anchor|counterpart|mitra)\w*\b.*(nominal|transaksi|saldo)"]
OFF_TOPIC = [r"\b(politik|pilpres|presiden|agama|judi|togel|slot|crypto pump|saham gorengan|resep|game)\b"]
BANK_TOPIC = [r"produk|rekening|tabungan|giro|deposito|kredit|kur|kartu|payroll|qris|edc|cib|garansi|l/c|"
              r"skbdn|sblc|nasabah|prospek|anchor|supplier|buyer|transaksi|saldo|pinjaman|investasi|reksa|bonds|"
              r"mobile banking|fleksi|kpr|prioritas|bank|kunjungan|pitch|rekomendasi|leakage|reaktivasi|cross.?sell"]
MASKS = [(re.compile(r"\b(C\d{6}|P\d{7}|Q\d{7}|L\d{5}|CIF\d{7})\b"), "[ID]"),
         (re.compile(r"\b\d{10,16}\b"), "[NOMOR]"),
         (re.compile(r"(\+62|\b08)\d{8,12}\b"), "[TELEPON]"),
         (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL]")]


@dataclass
class InputCheck:
    allowed: bool
    text: str
    reasons: list[str] = field(default_factory=list)


def mask(text: str) -> str:
    for pattern, token in MASKS:
        text = pattern.sub(token, text)
    return text


def check(text: str, free_text: bool = True) -> InputCheck:
    """free_text=False for button-triggered requests (F17): no user text to inspect."""
    reasons = []
    low = text.lower()
    if any(re.search(p, low) for p in INJECTION):
        reasons.append("pola prompt injection")
    if any(re.search(p, low) for p in DATA_REQUEST):
        reasons.append("permintaan kontak atau data pribadi pihak lain")
    if free_text and any(re.search(p, low) for p in OFF_TOPIC):
        reasons.append("di luar topik perbankan")
    if free_text and not any(re.search(p, low) for p in BANK_TOPIC):
        reasons.append("bukan pertanyaan tentang produk atau nasabah Bank")
    return InputCheck(allowed=not reasons, text=mask(text), reasons=reasons)
