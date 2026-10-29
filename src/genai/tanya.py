"""Tanya AI (F18): questions about Bank products, limited to banking topics, answered only from
the catalog (RAG) with sources. All four guardrail layers apply; every question is logged."""
from src.genai import llm, prompts, rag
from src.guardrails import audit_log, input_guard, output_guard

REFUSAL = "Maaf, saya hanya bisa membantu pertanyaan tentang produk dan layanan Bank untuk keperluan RM."


def answer(question: str, pengguna: str = "RM-demo") -> dict:
    gi = input_guard.check(question)
    flagged = llm.moderation_flagged(question)
    if flagged:
        gi.allowed, gi.reasons = False, gi.reasons + ["ditandai OpenAI Moderation"]
    if gi.allowed:  # semantic layer only when the rules let it through (saves a call on obvious attacks)
        label = llm.guard_label(gi.text)
        if label and label != "aman":
            gi.allowed, gi.reasons = False, gi.reasons + [f"klasifikasi LLM: {label.replace('_', ' ')}"]
    if not gi.allowed:
        out = {"jawaban": REFUSAL, "sumber": [], "diblokir": True, "alasan": gi.reasons}
        audit_log.write("Tanya AI", "", gi.text, gi.__dict__, [], out, {}, "diblokir input", pengguna)
        return out
    hits = rag.search(gi.text, 3)
    if hits.empty:
        out = {"jawaban": "Saya tidak tahu. Produk yang sesuai tidak ditemukan di katalog Bank.", "sumber": [], "diblokir": False}
        audit_log.write("Tanya AI", "", gi.text, gi.__dict__, [], out, {}, "tidak ditemukan", pengguna)
        return out
    context = hits[["Nama_Produk", "Fungsi_Manfaat", "Target_Nasabah", "Syarat_Umum", "URL_Sumber"]].to_dict("records")
    text, mode = None, "template"
    key, cached = llm.cached({"tanya": gi.text})
    if cached:
        text, mode = cached, "cache"
    else:
        cl = llm.client()
        if cl is not None:
            try:
                r = llm.chat(cl, messages=[
                    {"role": "system", "content": prompts.SYSTEM},
                    {"role": "user", "content": f"Pertanyaan: {gi.text}\nKatalog: {context}\nJawab singkat dan sertakan URL sumber."}])
                text, mode = r.choices[0].message.content, "llm"
            except Exception:
                text = None
        if text is None:
            text = "\n".join(f"- {c['Nama_Produk']}: {c['Fungsi_Manfaat']} Untuk: {c['Target_Nasabah']} (sumber: {c['URL_Sumber']})"
                             for c in context)
        else:
            llm.store(key, text)  # template answers are not cached, so the LLM is retried next time
    leaks = output_guard.leaks(text)
    if leaks:
        text = input_guard.mask(text)
    out = {"jawaban": text, "sumber": [c["URL_Sumber"] for c in context], "diblokir": False, "mode": mode}
    audit_log.write("Tanya AI", "", gi.text, gi.__dict__, [{"tool": "cari_katalog", "args": gi.text}], out,
                    {"kebocoran": leaks}, "lolos", pengguna)
    return out
