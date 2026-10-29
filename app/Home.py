"""Entry point: login, then a dashboard and page set per role (RM Retail, RM Wholesale/Corporate,
Management). Run with: streamlit run app/Home.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from app.components import auth  # noqa: E402
from app.components import data as D  # noqa: E402
from app.components import feedback  # noqa: E402
from app.components.ui import CSS  # noqa: E402
from src.genai import llm  # noqa: E402


@st.cache_resource
def _warm():
    llm.warm_up()   # once per app process: Gemma loads in the background
    return True


_warm()
st.set_page_config(page_title="RM Copilot Bank", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

user = auth.current_user()
if user is None:
    st.navigation([st.Page(auth.login_form, title="Masuk", icon=":material/login:")], position="hidden").run()
    st.stop()
if user.get("rm_id") == "auto":
    user["rm_id"] = D.default_rm()


def page(file: str, title: str, icon: str, default: bool = False):
    return st.Page(f"views/{file}", title=title, icon=icon, default=default)


tanya = page("tanya_ai.py", "Tanya AI produk", ":material/forum:")
PAGES = {
    "rm_retail": {
        "": [page("beranda_retail.py", "Beranda", ":material/home:", default=True)],
        "Kerja harian": [page("2_Rekomendasi_Nasabah.py", "Rekomendasi nasabah", ":material/recommend:"),
                         page("3_Prospek_Value_Chain.py", "Prospek pedagang dan karyawan", ":material/storefront:"),
                         tanya],
    },
    "rm_wholesale": {
        "": [page("beranda_wholesale.py", "Beranda", ":material/home:", default=True)],
        "Kerja harian": [page("1_Peluang_RM.py", "Peluang RM", ":material/target:"),
                         page("3_Prospek_Value_Chain.py", "Prospek perusahaan", ":material/domain_add:"),
                         page("4_Ekosistem.py", "Ekosistem anchor", ":material/hub:"),
                         tanya],
    },
    "manajemen": {
        "": [page("beranda_manajemen.py", "Beranda", ":material/home:", default=True)],
        "Kinerja bisnis": [page("6_Profit_Potential_Loss.py", "Profit dan potential loss", ":material/payments:"),
                           page("4_Ekosistem.py", "Ekosistem anchor", ":material/hub:")],
        "Tata kelola": [page("8_Model_dan_Monitoring.py", "Model dan monitoring", ":material/model_training:"),
                        page("5_Dashboard_KPI.py", "KPI model", ":material/insights:"),
                        page("7_Log_dan_Guardrail.py", "Log dan guardrail", ":material/shield:")],
    },
}

nav = st.navigation(PAGES[user["role"]])
auth.sidebar_user(user)
feedback.sidebar_button(user, nav.title)
nav.run()
