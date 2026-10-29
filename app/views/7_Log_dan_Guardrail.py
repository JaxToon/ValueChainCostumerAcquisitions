import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components import feedback  # noqa: E402
from app.components.ui import kpi, setup  # noqa: E402

setup("Log dan Guardrail", "Semua permintaan ke Tanya AI dan agent, hasil guardrail, dan keputusan RM. Uji serangan bisa dicoba di halaman Tanya AI (akun RM).")

st.markdown("### Log audit")
log = D.log_rows(1000)
c = st.columns(4)
kpi(c[0], "Permintaan", f"{len(log)}")
kpi(c[1], "Diblokir di input", f"{(log['status'] == 'diblokir input').sum()}", accent=True)
kpi(c[2], "Produk dicoret di output", f"{sum(len(g.get('diblokir', [])) for g in log['guardrail_output'])}", accent=True)
kpi(c[3], "Keputusan RM tercatat", f"{log['keputusan_rm'].notna().sum()}")
only = st.toggle("Hanya yang diblokir")
view = log[log["status"].str.contains("diblokir")] if only else log
st.dataframe(view[["id", "waktu", "halaman", "entitas", "input", "status", "keputusan_rm"]], hide_index=True, width="stretch")
st.caption("Lapisan: input (pola injection, topik, penyamaran ID), process (tool hanya-baca, maks 6 langkah, draft), "
           "output (katalog, kelayakan, sitasi, kebocoran, footer OJK), monitoring (log ini). ID disimpan tersamar.")

st.markdown("### Masukan pengguna")
fb = feedback.read()
if fb.empty:
    st.caption("Belum ada masukan. Penguji bisa mengisi lewat tombol 'Beri masukan' di sidebar.")
else:
    c = st.columns(2)
    kpi(c[0], "Masukan masuk", f"{len(fb)}")
    kpi(c[1], "Nilai rata-rata", f"{fb['nilai_1_5'].mean():.1f} / 5".replace(".", ",") if fb["nilai_1_5"].notna().any() else "-")
    st.dataframe(fb.sort_values("waktu", ascending=False), hide_index=True, width="stretch")
