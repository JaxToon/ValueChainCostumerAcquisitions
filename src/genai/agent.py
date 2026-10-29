"""RM Copilot Agent (F17) -> preparation pack H-1/H-2 (F22).

Triggered by the "Siapkan bahan kunjungan" button for one customer or prospect: no free
text. The generator (Gemma 4 E4B on Ollama by default, or OpenAI) plans the order of the six read-only tools (function
calling, at most 6 steps, re-plans when a product is dropped). When the model is
unreachable or returns an unusable draft, a fixed plan runs the same tools and fills a template, so the demo never breaks.
Every run goes through the output guardrail and into the audit log.
"""
import json
import re

import pandas as pd

from src.config import ROOT, settings
from src.genai import llm, prompts, tools
from src.guardrails import audit_log, input_guard, output_guard

SECTOR = pd.read_csv(ROOT / "synthetic_generator" / "reference" / "bps_pekerja_sektor_2025.csv").set_index("kode_kbli")["sektor"].to_dict()

TOOL_SPECS = [
    {"type": "function", "function": {"name": "ambil_profil", "description": "Profil, produk, fasilitas, saldo, sinyal transaksi",
                                      "parameters": {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]}}},
    {"type": "function", "function": {"name": "skor_produk", "description": "Produk teratas dari model dan alasannya",
                                      "parameters": {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]}}},
    {"type": "function", "function": {"name": "cek_kelayakan", "description": "Cek syarat katalog dan regulator untuk semua produk kandidat sekaligus",
                                      "parameters": {"type": "object", "properties": {"entity_id": {"type": "string"},
                                                                                      "produk": {"type": "array", "items": {"type": "string"}}},
                                                     "required": ["entity_id", "produk"]}}},
    {"type": "function", "function": {"name": "cari_katalog", "description": "Cari di katalog Bank (RAG): daftar nama produk yang layak sekaligus",
                                      "parameters": {"type": "object", "properties": {"query": {"type": "array", "items": {"type": "string"}}},
                                                     "required": ["query"]}}},
    {"type": "function", "function": {"name": "cek_compliance", "description": "Cek kebocoran data dan footer OJK pada teks",
                                      "parameters": {"type": "object", "properties": {"teks": {"type": "string"}}, "required": ["teks"]}}},
    {"type": "function", "function": {"name": "susun_draft", "description": "Kirim paket persiapan final",
                                      "parameters": {"type": "object", "required": ["ringkasan_bisnis", "peluang", "pertanyaan_validasi", "pitch_eksternal"],
                                                     "properties": {
                                                         **{k: {"type": "string"} for k in ["ringkasan_bisnis", "ringkasan_transaksi",
                                                                                            "pitch_eksternal", "catatan_internal"]},
                                                         **{k: {"type": "array", "items": {"type": "string"}} for k in
                                                            ["riwayat_produk", "pertanyaan_validasi", "sudut_pitching", "stakeholder"]},
                                                         "peluang": {"type": "array", "items": {"type": "object", "required": ["produk", "alasan", "sumber"],
                                                                                                 "properties": {"produk": {"type": "string"},
                                                                                                                "alasan": {"type": "string"},
                                                                                                                "sumber": {"type": "string"}}}}}}}},
]
LIST_FIELDS = ["riwayat_produk", "pertanyaan_validasi", "sudut_pitching", "stakeholder"]


def _normalize(pack: dict) -> dict | None:
    """Small models sometimes return lists as text; split them, and reject a draft without
    structured opportunities so the template takes over."""
    for k in LIST_FIELDS:
        v = pack.get(k)
        if isinstance(v, str):
            pack[k] = [s.strip(" -*•") for s in re.split(r"\n|(?<=\?)\s+", v) if s.strip(" -*•")]
    peluang = pack.get("peluang")
    if not isinstance(peluang, list) or not all(isinstance(p, dict) and p.get("produk") for p in peluang):
        return None
    return pack


def _template(entity_id: str, calls: list) -> dict:
    """Fixed plan: the same tools in a fixed order, sections filled from data and catalog."""
    def call(name, **kw):
        res = tools.TOOLS[name](**kw)
        calls.append({"tool": name, "args": kw, "hasil_ringkas": str(res)[:300]})
        return res

    prof = call("ambil_profil", entity_id=entity_id)
    recs = call("skor_produk", entity_id=entity_id)
    keep, dropped = [], []
    for r in recs:
        e = call("cek_kelayakan", entity_id=entity_id, produk=r["produk"])
        (keep if e["layak"] else dropped).append({**r, "alasan_tidak_layak": e["alasan"]})
    peluang, questions, angles, holders = [], [], [], []
    for r in keep[:3]:
        cat = tools.rag.product(r["produk"]) or (tools.cari_katalog(r["produk"], 1) or [{}])[0]
        why = [prompts.label(a) for a in r.get("alasan", [])] or [str(r.get("kebutuhan", "")).replace("_", " ")]
        if r.get("porsi_nasabah_mirip_memegang"):
            share = f"{r['porsi_nasabah_mirip_memegang']:.0%} nasabah dengan pola mirip memegang produk ini"
            if r.get("porsi_semua_nasabah"):
                share += f" ({r['porsi_nasabah_mirip_memegang'] / r['porsi_semua_nasabah']:.1f}x rata-rata nasabah)"
            why.append(share)
        peluang.append({"produk": r["produk"], "alasan": "; ".join(dict.fromkeys(w for w in why if w)), "sumber": cat.get("URL_Sumber")})
        if cat.get("Rekomendasikan_Jika"):
            questions.append(f"{r['produk']}: apakah benar {str(cat['Rekomendasikan_Jika']).rstrip('.').lower()}?")
        if cat.get("Fungsi_Manfaat"):
            angles.append(f"{r['produk']}: {str(cat['Fungsi_Manfaat']).split('.')[0]}.")
        holders.append(r.get("stakeholder") or tools.STAKEHOLDER.get(r["produk"], "RM"))
    sektor = SECTOR.get(str(prof.get("sektor")), prof.get("sektor"))
    trx = prof.get("transaksi_3bln")
    riwayat = [f"{p['produk']} ({p['status'].lower()})" for p in prof.get("produk", [])]
    ended = [p["produk"] for p in prof.get("produk", []) if p["status"] == "TIDAK AKTIF"]
    pitch = ("Kami melihat kebutuhan usaha Bapak/Ibu dapat didukung oleh " + ", ".join(p["produk"] for p in peluang)
             + ". Kami ingin memahami alur transaksi dan rencana usaha Bapak/Ibu untuk memastikan solusi yang paling sesuai.") if peluang else ""
    company = "korporasi" in prof["tipe"] or "perusahaan" in prof["tipe"]
    if company:
        summary = f"{prof['tipe'].replace('_', ' ').title()}, sektor {sektor}, {prof.get('provinsi')}" + (
            f", segmen {prof['segmen']}" if prof.get("segmen") else "")
        generic = ["Bagaimana alur pembayaran ke supplier dan dari buyer saat ini?",
                   "Bank mana yang dipakai untuk kebutuhan yang belum dilayani Bank, dan apa alasannya?"]
    else:
        summary = ", ".join(str(x) for x in [prof["tipe"].replace("_", " ").title(), prof.get("pekerjaan"),
                                              f"usia {prof['usia']:.0f}" if prof.get("usia") else None,
                                              f"penghasilan {prof['kisaran_pendapatan']}" if prof.get("kisaran_pendapatan") else None,
                                              prof.get("provinsi")] if x)
        generic = ["Apa rencana keuangan nasabah dalam 6 bulan ke depan?"]
    return tools.susun_draft(
        ringkasan_bisnis=summary,
        ringkasan_transaksi=(f"3 bulan terakhir: {trx['jumlah_counterparty']} counterpart, {trx['porsi_ke_bank_lain']} transaksi ke bank lain, masuk {trx['masuk']}, keluar {trx['keluar']}"
                             if trx else None),
        sinyal=prof.get("sinyal_f19"),
        riwayat_produk=riwayat or None,
        peluang=peluang,
        peluang_reaktivasi=ended or None,
        produk_dicoret=[{"produk": d["produk"], "alasan": d["alasan_tidak_layak"]} for d in dropped] or None,
        pertanyaan_validasi=questions + generic,
        sudut_pitching=angles,
        stakeholder=sorted(set(holders)),
        pitch_eksternal=pitch,
        catatan_internal="Draft untuk RM. Validasi kebutuhan langsung dengan nasabah sebelum menawarkan produk.")


def _llm(entity_id: str, calls: list) -> dict | None:
    cl = llm.client()
    if cl is None:
        return None
    cfg = settings()["llm"]
    msgs = [{"role": "system", "content": prompts.AGENT},
            {"role": "user", "content": f"Siapkan paket kunjungan untuk entitas {entity_id}."}]
    try:
        final = [t for t in TOOL_SPECS if t["function"]["name"] == "susun_draft"]
        for step in range(cfg["maks_langkah_agent"]):
            # Last step offers only susun_draft, so a small model cannot spend every step on lookups.
            last = step == cfg["maks_langkah_agent"] - 1
            if last:
                msgs.append({"role": "user", "content": prompts.FINAL_STEP})
            r = llm.chat(cl, messages=msgs, tools=final if last else TOOL_SPECS)
            m = r.choices[0].message
            if not m.tool_calls:
                break
            msgs.append(m.model_dump(exclude_none=True))
            for tc in m.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                if tc.function.name == "susun_draft":
                    calls.append({"tool": "susun_draft", "args": list(args)})
                    return _normalize(args)
                try:
                    res = tools.TOOLS[tc.function.name](**args)
                except (KeyError, TypeError) as e:  # unknown tool or wrong arguments: tell the model, keep going
                    res = {"error": f"panggilan tidak valid: {e}"}
                calls.append({"tool": tc.function.name, "args": args, "hasil_ringkas": str(res)[:300]})
                msgs.append({"role": "tool", "tool_call_id": tc.id,
                             "content": input_guard.mask(json.dumps(res, ensure_ascii=False, default=str))[:6000]})
    except Exception as e:
        calls.append({"tool": "error", "args": str(e)[:200]})
    return None


def run(entity_id: str, halaman: str = "Persiapan kunjungan") -> dict:
    key, hit = llm.cached({"agent": entity_id})
    mode = "cache"
    # The cache keeps the tool calls too, so a cached pack still shows (and is judged on) its context.
    pack, calls = (hit["paket"], hit["tool_calls"]) if isinstance(hit, dict) and "tool_calls" in hit else (hit, [])
    if pack is None:
        pack = _llm(entity_id, calls)
        mode = "llm"
        if pack is None:
            pack, mode = _template(entity_id, calls), "template"
        else:
            llm.store(key, {"paket": pack, "tool_calls": calls})  # template results are not cached, so the LLM is retried next time
    prof = tools.ambil_profil(entity_id)
    who = {k: prof.get(k) for k in ["usia", "pekerjaan", "kisaran_pendapatan"] if prof.get(k) is not None}
    if prof.get("segmen"):
        who["segmen_bank"] = prof["segmen"]
    peluang = pack.get("peluang") if isinstance(pack.get("peluang"), list) else []
    guard = output_guard.check([p["produk"] for p in peluang], who, str(pack.get("pitch_eksternal", "")),
                               [p.get("sumber") for p in peluang])
    # Opportunities must come from the model (skor_produk), not from the LLM's own ideas.
    model_products = {r["produk"] for r in tools.skor_produk(entity_id, k=5)}
    if model_products:
        for p in peluang:
            if p["produk"] in guard.approved and p["produk"] not in model_products:
                guard.approved.remove(p["produk"])
                guard.blocked.append({"produk": p["produk"], "alasan": "bukan rekomendasi model (ditambahkan LLM)"})
    pack["pitch_eksternal"] = guard.pitch
    pack["peluang"] = [p for p in peluang if p["produk"] in guard.approved]
    status = "lolos" if not guard.blocked else "sebagian diblokir"
    log_id = audit_log.write(halaman, entity_id, "tombol: Siapkan bahan kunjungan", {"jenis": "tombol, tanpa teks bebas"},
                             calls, pack, {"diblokir": guard.blocked, "catatan": guard.notes}, status)
    return {"paket": pack, "mode": mode, "tool_calls": calls, "guardrail": guard.__dict__, "log_id": log_id}
