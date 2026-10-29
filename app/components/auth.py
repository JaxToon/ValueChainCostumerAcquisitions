"""Simple role login for the demo (config/settings.yaml: akun_demo). Not a production login:
it only decides which dashboard and pages a person sees."""
import hashlib
import os

import streamlit as st

from src.config import settings

ROLES = {
    "rm_retail": {"label": "RM Retail", "icon": ":material/person:",
                  "fokus": "Nasabah perorangan: produk berikutnya (NBO), pedagang, dan karyawan payroll"},
    "rm_wholesale": {"label": "RM Wholesale / Corporate", "icon": ":material/apartment:",
                     "fokus": "Portofolio Commercial: lead counterpart, prospek perusahaan, dan ekosistem anchor"},
    "manajemen": {"label": "Manajemen / Stakeholder", "icon": ":material/monitoring:",
                  "fokus": "KPI, profit dan potential loss, kualitas model, serta kepatuhan guardrail"},
}


def accounts() -> list[dict]:
    return settings().get("akun_demo", [])


# For a shared link (for example ngrok): set RM_COPILOT_PASSWORD to replace the demo password of
# every account for that run, and the login page stops showing it.
SHARED_PASSWORD = os.environ.get("RM_COPILOT_PASSWORD")


def password_ok(acc: dict, password: str) -> bool:
    if SHARED_PASSWORD:
        return password == SHARED_PASSWORD
    return hashlib.sha256(password.encode()).hexdigest() == acc["password_sha256"]


def current_user() -> dict | None:
    return st.session_state.get("user")


def login_form():
    """Login screen; on success stores the account (without the password hash) in session state."""
    st.title("RM Copilot Bank")
    st.caption("Relationship & Value Chain Intelligence · data sintetis untuk capstone")
    left, right = st.columns([2, 3], gap="large")
    with left:
        with st.form("login", border=True):
            st.subheader("Masuk")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Masuk", type="primary", width="stretch"):
                acc = next((a for a in accounts() if a["username"] == username.strip() and password_ok(a, password)), None)
                if acc:
                    st.session_state["user"] = {k: v for k, v in acc.items() if k != "password_sha256"}
                    st.rerun()
                st.error("Username atau password salah.")
    with right:
        st.subheader("Akun demo")
        for acc in accounts():
            r = ROLES[acc["role"]]
            with st.container(border=True):
                st.markdown(f"{r['icon']} **{r['label']}** · `{acc['username']}`")
                st.caption(r["fokus"])
        if SHARED_PASSWORD:
            st.caption("Gunakan password yang dikirim tim kepada Anda. Login ini hanya memilih tampilan per peran.")
        else:
            st.caption("Password semua akun demo: `demo123`. Login ini hanya memilih tampilan per peran, bukan sistem keamanan produksi.")


def sidebar_user(user: dict):
    r = ROLES[user["role"]]
    with st.sidebar:
        st.markdown(f"{r['icon']} **{user['nama']}**  \n{r['label']}")
        if user.get("rm_id"):
            st.caption(f"Kode RM: {user['rm_id']}")
        if st.button("Keluar", icon=":material/logout:", width="stretch"):
            st.session_state.pop("user", None)
            st.rerun()
