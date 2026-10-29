"""'Beri masukan' button for user testing: a short form saved to outputs/masukan_pengguna.csv,
so feedback from testers (for example over an ngrok link) is collected in one place."""
from datetime import datetime

import pandas as pd
import streamlit as st

from src.config import path

FILE_NAME = "masukan_pengguna.csv"


def file():
    return path("outputs") / FILE_NAME


@st.dialog("Beri masukan", width="large")
def _form(user: dict, page_title: str):
    st.caption(f"Halaman: {page_title}. Jawaban Anda membantu kami memperbaiki aplikasi sebelum demo.")
    with st.form("masukan", border=False):
        nilai = st.feedback("stars", key="masukan_nilai")
        bingung = st.text_area("Apa yang membingungkan atau sulit dipakai?", key="masukan_bingung")
        berguna = st.text_area("Apa yang paling berguna untuk pekerjaan Anda?", key="masukan_berguna")
        saran = st.text_area("Saran lain (fitur, data, istilah)", key="masukan_saran")
        nama = st.text_input("Nama atau peran Anda (opsional)", key="masukan_nama")
        if st.form_submit_button("Kirim masukan", type="primary"):
            row = {"waktu": datetime.now().isoformat(timespec="seconds"), "akun": user.get("username"), "peran": user.get("role"),
                   "halaman": page_title, "nilai_1_5": (nilai + 1) if nilai is not None else None, "membingungkan": bingung,
                   "berguna": berguna, "saran": saran, "nama_penguji": nama}
            f = file()
            pd.DataFrame([row]).to_csv(f, mode="a", header=not f.exists(), index=False)
            st.success("Terima kasih, masukan tersimpan.")


def sidebar_button(user: dict, page_title: str):
    if st.sidebar.button("Beri masukan", icon=":material/rate_review:", width="stretch", key="btn_masukan"):
        _form(user, page_title)


def read() -> pd.DataFrame:
    f = file()
    return pd.read_csv(f) if f.exists() else pd.DataFrame()
