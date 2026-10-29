"""Contact tracker: which customer or prospect each RM has contacted and which became a deal.
Saved to outputs/status_kontak.csv (one row per change, the latest row per RM and entity counts),
so the home pages can show contacted and deal counts per RM next to the model's expectation."""
from datetime import datetime

import pandas as pd
import streamlit as st

from src.config import path

STATUS = ["Belum dihubungi", "Divalidasi ke anchor", "Dihubungi", "Deal", "Tidak tertarik"]
CONTACTED = {"Dihubungi", "Deal", "Tidak tertarik"}
FILE_NAME = "status_kontak.csv"


def file():
    return path("outputs") / FILE_NAME


def read() -> pd.DataFrame:
    """Latest status per (RM, entity)."""
    f = file()
    if not f.exists():
        return pd.DataFrame(columns=["waktu", "akun", "rm_nama", "peran", "entity_id", "tipe", "status"])
    df = pd.read_csv(f, dtype=str)
    return df.sort_values("waktu").drop_duplicates(["akun", "entity_id"], keep="last")


def account(user: dict) -> str:
    return user.get("rm_id") or user.get("username", "-")


def status_of(user: dict, entity_id: str) -> str:
    df = read()
    row = df[(df["akun"] == account(user)) & (df["entity_id"] == entity_id)]
    return row["status"].iloc[0] if len(row) else STATUS[0]


def widget(user: dict, entity_id: str, tipe: str, lead: bool = False):
    """Status picker + save button for one customer or prospect."""
    opts = STATUS if lead else [s for s in STATUS if s != "Divalidasi ke anchor"]
    now = status_of(user, entity_id)
    with st.container(horizontal=True, vertical_alignment="bottom"):
        new = st.selectbox("Status kontak", opts, index=opts.index(now) if now in opts else 0, key=f"kontak_{entity_id}",
                           help="Dicatat per RM. Jumlah dihubungi dan deal tampil di Beranda Anda dan di Beranda manajemen.")
        if st.button("Simpan status", key=f"kontak_simpan_{entity_id}", icon=":material/save:"):
            row = {"waktu": datetime.now().isoformat(timespec="seconds"), "akun": account(user), "rm_nama": user.get("nama", ""),
                   "peran": user.get("role", ""), "entity_id": entity_id, "tipe": tipe, "status": new}
            f = file()
            pd.DataFrame([row]).to_csv(f, mode="a", header=not f.exists(), index=False)
            st.success(f"Status tersimpan: {new}.")


def summary(df: pd.DataFrame) -> dict:
    contacted = df["status"].isin(CONTACTED)
    deal = df["status"].eq("Deal")
    n_c, n_d = int(contacted.sum()), int(deal.sum())
    return {"dihubungi": n_c, "deal": n_d, "tingkat_deal": n_d / n_c if n_c else None,
            "divalidasi": int(df["status"].eq("Divalidasi ke anchor").sum())}


def mine(user: dict) -> dict:
    df = read()
    return summary(df[df["akun"] == account(user)])


def per_rm() -> pd.DataFrame:
    """Contacted, deal, and deal rate per RM (management view)."""
    df = read()
    if df.empty:
        return pd.DataFrame(columns=["rm", "peran", "dihubungi", "deal", "tingkat_deal"])
    rows = [{"rm": f"{g['rm_nama'].iloc[-1]} ({akun})", "peran": g["peran"].iloc[-1], **summary(g)} for akun, g in df.groupby("akun")]
    return pd.DataFrame(rows).sort_values(["deal", "dihubungi"], ascending=False)
