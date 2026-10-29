import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components import kontak  # noqa: E402
from app.components.pack import prep_button  # noqa: E402
from app.components.ui import kpi, pct, rupiah, setup  # noqa: E402
from src.config import settings  # noqa: E402

setup("Prospek Value Chain", "Calon nasabah yang terlihat dari transaksi nasabah Bank, diurutkan dari peluang tertinggi menjadi nasabah dalam 6 bulan.")

# Each role sees its own prospect types: retail RMs work traders and payroll employees,
# wholesale RMs work companies; management sees all.
user = st.session_state.get("user", {})
allowed = {"rm_retail": ["pedagang", "karyawan"], "rm_wholesale": ["perusahaan"]}.get(user.get("role"), ["perusahaan", "pedagang", "karyawan"])
LABEL = {"perusahaan": "Perusahaan (RM Commercial)", "pedagang": "Pedagang (program anchor)", "karyawan": "Karyawan (Payroll Korporasi)"}
UNIT = {"perusahaan": "perusahaan", "pedagang": "pedagang", "karyawan": "orang"}
tipe = allowed[0] if len(allowed) == 1 else st.segmented_control("Tipe calon nasabah", allowed, default=allowed[0], format_func=LABEL.get,
                                                                    key="pros_tipe") or allowed[0]
unit = UNIT[tipe]
lb = settings()["windows"]["lookback_bulan"]
p = D.prospects()
p = p[p["tipe_prospek"] == tipe].sort_values("peringkat_dalam_tipe").copy()
p["nominal_bulanan"] = np.expm1(p["log_nominal_total"]) / lb          # feature = total over the lookback months
base = D.base_rate()["tipe"].get(tipe, p["skor_tipe"].mean())


def num(x) -> str:
    return f"{x:,.0f}".replace(",", ".")


st.markdown(f"<div class='note'>Peluang 6 bulan = perkiraan kemungkinan calon membuka rekening atau produk pertamanya di Bank dalam 6 bulan ke depan. "
            f"Rata-rata semua {unit} di daftar ini: <b>{pct(base)}</b>.</div>", unsafe_allow_html=True)
with st.expander("Apa itu peluang 6 bulan dan dari mana angkanya?", icon=":material/help:"):
    st.markdown(D.PELUANG_6_BULAN)

with st.container(border=True):
    st.markdown("**Rencana kerja**")
    cap = st.number_input(f"Berapa {unit} yang sanggup Anda hubungi periode ini?", 5, 500, 20 if tipe == "perusahaan" else 50, 5, key=f"cap_{tipe}")
    top = p.head(int(cap))
    exp_list, exp_rand = top["skor_tipe"].sum(), cap * base
    log = kontak.read()
    k = kontak.summary(log[(log["akun"] == kontak.account(user)) & (log["tipe"] == tipe)])
    c = st.columns(4)
    kpi(c[0], "Calon nasabah", f"{num(len(p))} {unit}", f"rata-rata peluang 6 bulan {pct(base)}")
    kpi(c[1], f"Bila {num(cap)} teratas dihubungi", f"± {exp_list:.1f} {unit}".replace(".", ","),
        f"perkiraan jadi nasabah · pilih acak hanya ± {exp_rand:.1f} ({exp_list / max(exp_rand, 1e-9):.1f}x lebih banyak)".replace(".", ","), accent=True)
    kpi(c[2], f"Nilai transaksi {num(cap)} teratas", f"{rupiah(top['nominal_bulanan'].sum())}/bulan",
        "arus dana yang bisa dibawa ke Bank bila mereka bergabung")
    kpi(c[3], "Dihubungi / deal (Anda)", f"{k['dihubungi']} / {k['deal']} {unit}",
        f"tingkat deal {pct(k['tingkat_deal'])}" if k["tingkat_deal"] is not None else f"perkiraan deal ± {pct(top['skor_tipe'].mean())}")

jalur = {"perusahaan": "Kunjungan RM setelah validasi ke anchor atau referral; tidak ada kontak dari data transaksi.",
         "pedagang": "Lewat program anchor (anchor mengajak jaringan pedagangnya); produk pembuka Tabungan Plus Bisnis, lalu QRIS dan KUR Mikro.",
         "karyawan": "Lewat Payroll Korporasi perusahaan pemberi kerja; tidak ada kontak langsung ke perorangan."}[tipe]
st.info(f"Jalur kontak: {jalur}")

status = kontak.read()
status = status[status["akun"] == kontak.account(user)].set_index("entity_id")["status"]
view = p.head(200).assign(status=lambda d: d["entity_id"].map(status).fillna("Belum dihubungi"))
cols = ["peringkat_dalam_tipe", "entity_id", "nama", "sektor_nama", "skor_tipe", "nominal_bulanan", "status"]
if tipe != "perusahaan":       # persons have no display name in the synthetic data (ID only)
    cols.remove("nama")
st.dataframe(view[cols], hide_index=True, width="stretch",
             column_config={"peringkat_dalam_tipe": "Urutan", "entity_id": "ID", "nama": "Nama", "sektor_nama": "Sektor",
                            "skor_tipe": st.column_config.ProgressColumn("Peluang 6 bulan", min_value=0, max_value=1, format="percent"),
                            "nominal_bulanan": st.column_config.NumberColumn("Transaksi per bulan (Rp)", format="localized"),
                            "status": "Status kontak"})
st.caption(f"Skala peluang 0–100%. Transaksi per bulan = rata-rata {lb} bulan terakhir yang terlihat bank.")

st.markdown("### Detail calon nasabah")
pid = st.selectbox("Calon nasabah", view["entity_id"].tolist(), key=f"pros_pick_{tipe}",
                   format_func=lambda x: f"{view.set_index('entity_id').at[x, 'nama']} · peluang {pct(view.set_index('entity_id').at[x, 'skor_tipe'], 0)}")
row = view.set_index("entity_id").loc[pid]
c = st.columns(3)
kpi(c[0], "Peluang 6 bulan", pct(row["skor_tipe"]), f"rata-rata {unit} lain {pct(base)} · {row['skor_tipe'] / max(base, 1e-9):.1f}x".replace(".", ","), accent=True)
kpi(c[1], "Urutan", f"#{int(row['peringkat_dalam_tipe'])} dari {num(len(p))}", f"di antara semua {unit}")
kpi(c[2], "Transaksi per bulan", rupiah(row["nominal_bulanan"]), f"rata-rata {lb} bulan terakhir")

st.markdown("**Kenapa peluangnya segini** (3 alasan terbesar dari model, dengan angka di baliknya)")
ex = D.load("explain", f"akuisisi_{tipe}_lokal")
r = ex[ex["entity_id"] == pid]
if len(r):
    for i in range(1, 4):
        st.markdown(f"{i}. " + D.reason_detail(pid, r[f"alasan_{i}"].iloc[0], float(r[f"nilai_{i}"].iloc[0]), tipe, p))
else:
    st.caption("Alasan belum tersedia untuk calon ini.")

tr = D.load("clean", "transfers")
e = tr[(tr["from_id"] == pid) | (tr["to_id"] == pid)]
e = e.assign(lawan=e["from_id"].where(e["to_id"] == pid, e["to_id"]))
comp = D.load("clean", "companies").set_index("company_id")
paths = e.groupby("lawan").agg(nominal=("total_nominal_rp", "sum"), bulan=("bulan_ke", "nunique")).sort_values("nominal", ascending=False).head(5)
paths["mitra"] = paths.index.map(lambda x: comp["nama_samaran"].get(x, x))
paths["anchor"] = paths.index.map(lambda x: bool(comp["is_anchor"].get(x, False)))
st.markdown("**Mitra Bank terbesar yang bisa jadi jalur perkenalan**")
st.dataframe(paths.reset_index(drop=True)[["mitra", "anchor", "nominal", "bulan"]], hide_index=True, width="stretch",
             column_config={"mitra": "Mitra", "anchor": st.column_config.CheckboxColumn("Anchor Bank"),
                            "nominal": st.column_config.NumberColumn("Nilai transaksi (Rp)", format="localized"),
                            "bulan": "Bulan bertransaksi"})

st.markdown("**Status kontak**")
kontak.widget(user, pid, tipe)
prep_button(pid, "Prospek Value Chain", f"pros_{pid}")
