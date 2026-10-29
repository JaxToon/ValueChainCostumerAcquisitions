import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components import kontak  # noqa: E402
from app.components.pack import prep_button  # noqa: E402
from app.components.ui import badge, kpi, pct, setup  # noqa: E402
from src.genai import prompts, tools  # noqa: E402

setup("Rekomendasi Nasabah", "Pilih nasabah, lihat tiga produk yang paling cocok beserta alasannya, catat status kontak, "
      "lalu siapkan bahan kunjungan di bagian bawah.")

s = D.load("scores", "nbo_test")
best = s.sort_values("skor", ascending=False).drop_duplicates("person_id").head(300).set_index("person_id")
top_people = best.index.tolist()
pending = st.session_state.pop("nbo_pending", None)     # picked on the home page, applied once
if pending:
    if pending not in top_people:
        top_people = [pending] + top_people
    st.session_state["nbo_select"] = pending

with st.container(border=True):
    st.markdown("**1. Pilih nasabah** · daftar diurutkan dari peluang beli tertinggi (300 teratas); ketik ID untuk mencari.")
    pid = st.selectbox("Nasabah", top_people, key="nbo_select", label_visibility="collapsed",
                       format_func=lambda x: (f"{x} · {best.at[x, 'produk']} · peluang {pct(best.at[x, 'skor'], 0)}"
                                              if x in best.index else x))

prof = tools.ambil_profil(pid)
c = st.columns(4)
kpi(c[0], "Usia", f"{prof.get('usia', 0):.0f} tahun")
kpi(c[1], "Pekerjaan", str(prof.get("pekerjaan")))
kpi(c[2], "Kisaran penghasilan", str(prof.get("kisaran_pendapatan")))
held = [x.replace("_", " ").title() for x in prof.get("produk_dipegang", [])]
kpi(c[3], "Produk dipegang", f"{len(held)} produk", ", ".join(held))

st.markdown("### 2. Top 3 rekomendasi")
st.caption("Peluang = perkiraan kemungkinan nasabah membeli produk itu dalam 1 bulan ke depan (0–100%).")
for r in tools.skor_produk(pid):
    e = tools.cek_kelayakan(pid, r["produk"])
    status = badge("Layak", "ok") if e["layak"] else badge(f"Diblokir: {e['alasan']}", "block")
    reasons = "; ".join(dict.fromkeys(prompts.label(a) for a in r["alasan"]))
    mirip = ""
    if r.get("porsi_nasabah_mirip_memegang") is not None:
        mirip = f"<br><span class='note'>{pct(r['porsi_nasabah_mirip_memegang'])} dari 50 nasabah paling mirip memegang produk ini"
        if r.get("porsi_semua_nasabah"):
            mirip += f" (rata-rata semua nasabah {pct(r['porsi_semua_nasabah'])}, {r['porsi_nasabah_mirip_memegang'] / r['porsi_semua_nasabah']:.1f}x)"
        mirip += "</span>"
    st.markdown(f"<div class='card'><b>{r['produk']}</b> · peluang beli {pct(r['skor'])} {status}<br>{reasons}{mirip}</div>", unsafe_allow_html=True)

st.markdown("### 3. Status kontak")
kontak.widget(st.session_state.get("user", {}), pid, "nasabah_ritel")

st.markdown("### 4. Bahan kunjungan")
prep_button(pid, "Rekomendasi Nasabah", f"nbo_{pid}")
