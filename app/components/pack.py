"""Render the F22 preparation pack and the RM decision buttons (human in the loop), in the order
an RM prepares a visit: who the customer is, what to offer, what to ask, what to send."""
import streamlit as st

from app.components.ui import badge
from src.genai import agent
from src.guardrails import audit_log

MODE = {"llm": ("Disusun AI", "ok"), "cache": ("Disusun AI (tersimpan)", "ok"),
        "template": ("Format standar: AI sedang tidak tersedia", "warn")}
SIGNAL = {"counterpart_baru": "mitra baru bernilai besar", "transaksi_besar": "transaksi besar", "pindah_bank": "dana pindah bank",
          "counterparty_ganti_bank": "mitra ganti bank", "counterpart_berulang": "mitra rutin"}


def prep_button(entity_id: str, page: str, key: str):
    if st.button("Siapkan bahan kunjungan", key=f"btn_{key}", type="primary", icon=":material/description:",
                 help="AI membaca data nasabah, memilih produk yang layak dari katalog Bank, lalu menyusun bahan kunjungan. "
                      "Hasilnya dicek kepatuhan sebelum tampil."):
        with st.spinner("Menyusun bahan kunjungan, sekitar 15–30 detik..."):
            st.session_state[f"pack_{key}"] = agent.run(entity_id, page)
    res = st.session_state.get(f"pack_{key}")
    if res:
        render(res, key)


def render(res: dict, key: str):
    p, g = res["paket"], res["guardrail"]
    label, kind = MODE[res["mode"]]
    check = badge(f"{len(g['blocked'])} produk tidak ditawarkan (tidak memenuhi syarat)", "warn") if g["blocked"] else badge("Sudah dicek kepatuhan", "ok")
    st.markdown(badge(label, kind) + check, unsafe_allow_html=True)

    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.markdown("#### 1. Tentang nasabah")
        st.markdown(p.get("ringkasan_bisnis", "-"))
        if p.get("ringkasan_transaksi"):
            st.markdown(p["ringkasan_transaksi"])
        if p.get("sinyal"):
            st.markdown("**Yang terlihat di transaksi:** " + ", ".join(f"{SIGNAL.get(k, k.replace('_', ' '))} ({v})" for k, v in p["sinyal"].items()))
        st.markdown("#### 2. Produk yang bisa ditawarkan")
        for o in p.get("peluang", []):
            with st.container(border=True):
                st.markdown(f"**{o['produk']}**  \n{o['alasan']}")
                st.caption(f"Sumber katalog: {o.get('sumber')}")
        for d in g["blocked"]:
            st.markdown(badge(f"Tidak ditawarkan: {d['produk']}", "block") + f" <span class='note'>{d['alasan']}</span>", unsafe_allow_html=True)
        if p.get("peluang_reaktivasi"):
            st.markdown("**Bisa diaktifkan lagi:** " + ", ".join(p["peluang_reaktivasi"]))
    with c2:
        st.markdown("#### 3. Pertanyaan saat kunjungan")
        for q in p.get("pertanyaan_validasi", []):
            st.markdown(f"- {q}")
        if p.get("stakeholder"):
            st.markdown("**Ajak dalam kunjungan:** " + ", ".join(p["stakeholder"]))
        if p.get("riwayat_produk"):
            with st.expander("Riwayat produk nasabah"):
                for r in p["riwayat_produk"]:
                    st.markdown(f"- {r}")

    st.markdown("#### 4. Pesan untuk nasabah")
    st.caption("Draft ini sudah dicek: tanpa data nasabah lain, tanpa janji imbal hasil, dengan footer OJK. Ubah bila perlu, lalu putuskan.")
    text = st.text_area("Pesan", p.get("pitch_eksternal", ""), key=f"pitch_{key}", height=120, label_visibility="collapsed")
    with st.container(horizontal=True):
        for label_btn, decision, btype in [("Setujui pesan", "Setujui", "primary"), ("Simpan dengan perubahan saya", "Edit", "secondary"),
                                           ("Tolak", "Tolak", "secondary")]:
            if st.button(label_btn, key=f"{decision}_{key}", type=btype):
                audit_log.decide(res["log_id"], decision, text if decision == "Edit" else "")
                st.success(f"Keputusan tercatat: {decision}. Bisa dilihat manajemen di halaman Log.")
    with st.expander("Detail teknis (langkah AI dan catatan kepatuhan)"):
        st.caption(f"Mode: {res['mode']} · {len(res['tool_calls'])} langkah tool")
        for n in g["notes"]:
            st.markdown(f"- {n}")
        for i, c in enumerate(res["tool_calls"], 1):
            args = ", ".join(f"{k}={v}" for k, v in c["args"].items()) if isinstance(c["args"], dict) else c["args"]
            st.markdown(f"**{i}. `{c['tool']}`** ({args})")
            if c.get("hasil_ringkas"):
                st.caption(c["hasil_ringkas"])
