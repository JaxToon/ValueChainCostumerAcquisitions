"""Shared look for every page (design: ui-ux-pro-max 'Data-Dense Dashboard', Bank teal + orange
accent, text contrast >= 4.5:1). The app only reads files; it never imports Neo4j."""
import re

import streamlit as st

TEAL, TEAL_DARK, ORANGE, INK, MUTED, BG, BORDER, RED, GREEN = (
    "#006D77", "#004E57", "#E8601C", "#14303A", "#4A5D66", "#F6F8F9", "#D8E2E5", "#C62828", "#2E7D32")
PLOTLY = dict(template="simple_white", colorway=[TEAL, ORANGE, "#5C7C89", "#9BB7BF", "#B04A14"],
              font=dict(family="Fira Sans, Segoe UI, sans-serif", size=13, color=INK), margin=dict(l=10, r=10, t=40, b=10))

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500&family=Fira+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Fira Sans', 'Segoe UI', sans-serif; color: {INK}; }}
.stApp {{ background: {BG}; }}
h1, h2, h3 {{ color: {TEAL_DARK}; letter-spacing: -0.01em; }}
section[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid {BORDER}; }}
.kpi {{ background:#FFFFFF; border:1px solid {BORDER}; border-left:4px solid {TEAL}; border-radius:8px; padding:12px 14px; }}
.kpi .label {{ font-size:13px; color:{MUTED}; }}
.kpi .value {{ font-family:'Fira Code', monospace; font-size:24px; font-weight:500; color:{INK}; }}
.kpi .value small {{ font-family:'Fira Sans', sans-serif; font-size:14px; font-weight:500; color:{MUTED}; margin-left:4px; }}
.kpi .delta {{ font-size:12px; color:{MUTED}; }}
.kpi.accent {{ border-left-color:{ORANGE}; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:600; margin-right:4px; white-space:nowrap; }}
.badge.ok {{ background:#E3F1E4; color:{GREEN}; }} .badge.warn {{ background:#FDEBDF; color:#9A3F0F; }}
.badge.block {{ background:#FBE3E3; color:{RED}; }} .badge.info {{ background:#E0EFF1; color:{TEAL_DARK}; }}
.note {{ font-size:13px; color:{MUTED}; }}
.card {{ background:#FFFFFF; border:1px solid {BORDER}; border-radius:8px; padding:14px 16px; margin-bottom:10px; }}
</style>
"""


def setup(title: str, subtitle: str = ""):
    st.set_page_config(page_title=f"{title} | RM Copilot", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.markdown(f"<div class='note'>{subtitle}</div>", unsafe_allow_html=True)
    st.sidebar.markdown("**RM Copilot Bank**  \nRelationship & Value Chain Intelligence")
    st.sidebar.caption("Data sintetis untuk capstone. Rekomendasi adalah draft; RM yang memutuskan.")


# Splits "1.695 perusahaan" / "Rp31,7 M/bulan" into the number and a smaller unit.
UNIT = re.compile(r"^(.*?\d[\d.,]*(?:\s(?:jt|M|T)\b)?)\s*((?!(?:jt|M|T)\b)/?[A-Za-z].*)?$")


def kpi(col, label: str, value: str, delta: str = "", accent: bool = False):
    m = UNIT.match(value)
    if m and m.group(2):
        value = f"{m.group(1)}<small>{m.group(2)}</small>"
    col.markdown(f"<div class='kpi{' accent' if accent else ''}'><div class='label'>{label}</div>"
                 f"<div class='value'>{value}</div><div class='delta'>{delta}</div></div>", unsafe_allow_html=True)


def badge(text: str, kind: str = "info") -> str:
    return f"<span class='badge {kind}'>{text}</span>"


def rupiah(x) -> str:
    if x is None or x != x:
        return "-"
    a, sign = abs(float(x)), "-" if x < 0 else ""
    for div, unit in [(1e12, " T"), (1e9, " M"), (1e6, " jt")]:
        if a >= div:
            return f"{sign}Rp{a / div:.1f}{unit}".replace(".", ",")
    return f"{sign}Rp{a:,.0f}".replace(",", ".")


def pct(x: float, d: int = 1) -> str:
    return f"{x:.{d}%}".replace(".", ",")
