import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components import kontak  # noqa: E402
from app.components.ui import kpi, pct, setup  # noqa: E402

user = st.session_state.get("user", {})
setup(f"Selamat datang, {user.get('nama', 'RM')}", "Mulai dari rencana kerja di bawah; klik baris nasabah mana pun untuk melihat produk yang cocok dan menyiapkan kunjungan.")

s = D.load("scores", "nbo_test")
best = s.sort_values("skor", ascending=False).drop_duplicates("person_id").copy()
nas = D.load("clean", "nasabah").set_index("person_id")
best["profil"] = best["person_id"].map(lambda i: f"{nas.at[i, 'pekerjaan']}, {nas.at[i, 'usia_bulan1']:.0f} th, {nas.at[i, 'kisaran_pendapatan']}"
                                      if i in nas.index else "-")
p = D.prospects()
anchor = p[p["tipe_prospek"].isin(["pedagang", "karyawan"])]
ready = best[best["skor"] >= 0.3]
k = kontak.mine(user)


def num(n) -> str:
    return f"{n:,.0f}".replace(",", ".")


c = st.columns(4)
kpi(c[0], "Nasabah siap ditawari", f"{num(len(ready))} nasabah",
    f"peluang beli bulan depan ≥ 30% · rata-rata semua nasabah {pct(best['skor'].mean())}", accent=True)
kpi(c[1], "Sudah Anda hubungi", f"{num(k['dihubungi'])} orang", f"nasabah dan calon · target {num(len(ready))} nasabah prioritas")
kpi(c[2], "Deal", f"{num(k['deal'])} orang",
    (f"tingkat deal {pct(k['tingkat_deal'])}" if k["tingkat_deal"] is not None else "belum ada yang dihubungi")
    + f" · perkiraan model {pct(ready['skor'].mean())}")
kpi(c[3], "Calon nasabah lewat anchor", f"{num(len(anchor))} orang",
    f"perkiraan {num(anchor['skor_tipe'].sum())} orang jadi nasabah dalam 6 bulan")

with st.expander("Apa arti angka peluang?", icon=":material/help:"):
    st.markdown("**Peluang beli bulan depan** (nasabah) = perkiraan kemungkinan nasabah **membeli produk itu dalam 1 bulan ke depan**. "
                "Dihitung dari produk yang sudah dipegang, usia, pekerjaan, kisaran penghasilan, lama menjadi nasabah, dan produk yang "
                "dipakai nasabah dengan pola transaksi mirip. Contoh: 40% = dari 10 nasabah serupa, sekitar 4 membeli.")
    st.markdown(D.PELUANG_6_BULAN)
    st.caption("Status 'Dihubungi' dan 'Deal' Anda isi sendiri di halaman Rekomendasi nasabah atau Prospek; angka di atas dihitung dari situ.")


def go_customer(pid: str):
    st.session_state["nbo_pending"] = pid
    st.switch_page("views/2_Rekomendasi_Nasabah.py")


st.subheader("Rencana kerja hari ini")
with st.container(border=True):
    first = best.iloc[0]
    st.markdown(f"**1. Hubungi nasabah dengan peluang tertinggi.** {first['person_id']} ({first['profil']}) "
                f"paling mungkin mengambil **{first['produk']}** ({pct(first['skor'], 0)} peluang beli bulan depan).")
    if st.button(f"Lihat rekomendasi {first['person_id']}", key="r_step1", type="primary", icon=":material/person_search:"):
        go_customer(first["person_id"])
    left_n = max(len(ready) - k["dihubungi"], 0)
    st.markdown(f"**2. Kerjakan daftar prioritas.** Masih {num(left_n)} nasabah prioritas yang belum dihubungi; "
                f"bila semua dihubungi, perkiraan {num(ready['skor'].sum())} nasabah membeli.")
    st.markdown("**3. Ajak calon nasabah lewat anchor.** Pedagang yang membeli dari distributor Bank dan karyawan perusahaan payroll.")
    st.page_link("views/3_Prospek_Value_Chain.py", label="Buka daftar pedagang dan karyawan", icon=":material/arrow_forward:")

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Nasabah prioritas")
    status = kontak.read()
    status = status[status["akun"] == kontak.account(user)].set_index("entity_id")["status"]
    view = best.head(15).assign(status=lambda d: d["person_id"].map(status).fillna("Belum dihubungi"))
    ev = st.dataframe(view[["person_id", "profil", "produk", "skor", "status"]], hide_index=True, width="stretch",
                      on_select="rerun", selection_mode="single-row", key="home_retail",
                      column_config={"person_id": "Nasabah", "profil": "Profil", "produk": "Produk berikutnya",
                                     "skor": st.column_config.ProgressColumn("Peluang beli bulan depan", min_value=0, max_value=1, format="percent"),
                                     "status": "Status kontak"})
    if ev.selection.rows:
        go_customer(view.iloc[ev.selection.rows[0]]["person_id"])
    st.caption("Nama nasabah tidak ditampilkan (data sintetis); di sistem nyata kolom ini memakai nama dan CIF.")
with right:
    st.subheader("Calon nasabah lewat anchor")
    for tipe, label in [("pedagang", "Pedagang (program anchor)"), ("karyawan", "Karyawan (Payroll Korporasi)")]:
        t = p[p["tipe_prospek"] == tipe].sort_values("peringkat_dalam_tipe").head(5)
        with st.container(border=True):
            st.markdown(f"**{label}** · rata-rata peluang semua {tipe} {pct(D.base_rate()['tipe'].get(tipe, 0))}")
            st.dataframe(t[["entity_id", "skor_tipe"]], hide_index=True, width="stretch",
                         column_config={"entity_id": "Calon nasabah",
                                        "skor_tipe": st.column_config.ProgressColumn("Peluang 6 bulan", min_value=0, max_value=1, format="percent")})
    st.page_link("views/tanya_ai.py", label="Tanya AI tentang produk", icon=":material/forum:")

team = kontak.per_rm()
team = team[team["peran"] == "rm_retail"]
if len(team) > 1:
    st.subheader("Aktivitas tim RM retail")
    st.dataframe(team.drop(columns="peran"), hide_index=True, width="stretch",
                 column_config={"rm": "RM", "dihubungi": "Dihubungi (nasabah)", "deal": "Deal (nasabah)",
                                "tingkat_deal": st.column_config.NumberColumn("Tingkat deal", format="percent"), "divalidasi": None})
