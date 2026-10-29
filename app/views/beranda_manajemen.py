import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components import kontak  # noqa: E402
from app.components.ui import PLOTLY, TEAL, kpi, pct, rupiah, setup  # noqa: E402
from src.impact import profit as P  # noqa: E402

user = st.session_state.get("user", {})
setup(f"Selamat datang, {user.get('nama', 'Manajemen')}", "Beranda pimpinan wilayah: potensi profit, aktivitas RM, dan peluang per kanwil. "
      "Kualitas model dan kepatuhan AI ada di menu Tata kelola.")

PROGRAMS = {"nbo": ("NBO ritel (produk berikutnya)", "penawaran"), "akuisisi": ("Akuisisi calon nasabah", "calon"),
            "wholesale_cross_sell_wholesale": ("Cross-sell wholesale", "perusahaan")}
WORK_PAGES = ["Peluang RM", "Rekomendasi Nasabah", "Prospek Value Chain", "Persiapan kunjungan"]   # real RM use, not tests or eval


def num(x) -> str:
    return f"{x:,.0f}".replace(",", ".")


@st.cache_data
def program_table() -> pd.DataFrame:
    rows = []
    for eng, (label, unit) in PROGRAMS.items():
        m, b = P.cumulative(eng, "nilai_harapan"), P.cumulative(eng, "skor_baseline")
        bm, bb = m[m["terbaik"]].iloc[0], b[b["terbaik"]].iloc[0]
        rows.append({"program": label, "dihubungi": f"{num(bm['dihubungi'])} {unit}", "konversi": f"{num(bm['konversi'])} {unit}",
                     "profit_model": bm["profit_bersih"], "profit_lama": bb["profit_bersih"], "tambahan": bm["profit_bersih"] - bb["profit_bersih"]})
    return pd.DataFrame(rows)


@st.cache_data
def by_kanwil() -> pd.DataFrame:
    """Expected new customers in 6 months (sum of calibrated chances) and prospects per regional office."""
    p = D.prospects()
    prov = pd.concat([D.load("clean", "companies").set_index("company_id")["provinsi"], D.load("clean", "persons").set_index("person_id")["provinsi"]])
    p = p.assign(kanwil=p["entity_id"].map(prov).map(D.kanwil_map()["kanwil"]))
    return (p.groupby("kanwil").agg(calon=("entity_id", "size"), perkiraan_nasabah_baru=("skor_tipe", "sum"))
            .reset_index().sort_values("perkiraan_nasabah_baru", ascending=False))


prog = program_table()
k = kontak.summary(kontak.read())
ms = P.mis_selling_prevented()
c = st.columns(4)
kpi(c[0], "Potensi profit bersih", rupiah(prog["profit_model"].sum()), f"cara lama {rupiah(prog['profit_lama'].sum())} · 3 program", accent=True)
kpi(c[1], "Tambahan profit vs cara lama", rupiah(prog["tambahan"].sum()), "bila RM menghubungi sesuai urutan sistem")
kpi(c[2], "Aktivitas RM: dihubungi / deal", f"{num(k['dihubungi'])} / {num(k['deal'])}",
    f"tingkat deal {pct(k['tingkat_deal'])}" if k["tingkat_deal"] is not None else "belum ada kontak tercatat")
kpi(c[3], "Salah jual dicegah", rupiah(ms["rugi_dicegah"]), f"{ms['kasus_diblokir']} rekomendasi tidak layak diblokir", accent=True)

st.subheader("Potensi per program")
st.dataframe(prog, hide_index=True, width="stretch",
             column_config={"program": "Program", "dihubungi": "Jumlah ideal dihubungi", "konversi": "Perkiraan konversi",
                            "profit_model": st.column_config.NumberColumn("Profit bersih (Rp)", format="localized"),
                            "profit_lama": st.column_config.NumberColumn("Cara lama (Rp)", format="localized"),
                            "tambahan": st.column_config.NumberColumn("Tambahan (Rp)", format="localized")})
st.caption("Jumlah ideal = titik di mana selisih pendapatan dan biaya kontak paling lebar. Angka hanya asumsi, bisa berbeda di lapangan."
           "simulasi dan grafiknya di halaman Profit dan potential loss.")
st.page_link("views/6_Profit_Potential_Loss.py", label="Buka simulasi profit dan potential loss", icon=":material/payments:")

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Peluang nasabah baru per kanwil (6 bulan)")
    kw = by_kanwil()
    fig = px.bar(kw, x="perkiraan_nasabah_baru", y="kanwil", orientation="h", color_discrete_sequence=[TEAL],
                 hover_data={"calon": True}, labels={"perkiraan_nasabah_baru": "Perkiraan calon jadi nasabah", "kanwil": "", "calon": "Calon"})
    fig.update_layout(**PLOTLY, height=460, yaxis=dict(categoryorder="total ascending"))
    st.plotly_chart(fig, width="stretch")
    st.caption("Jumlah peluang 6 bulan semua calon (perusahaan, pedagang, karyawan) di wilayah kanwil, dari data transaksi nasabah Bank.")
with right:
    st.subheader("Aktivitas per RM")
    team = kontak.per_rm()
    if team.empty:
        st.caption("Belum ada status kontak. RM mengisi 'Status kontak' di halaman kerja harian mereka.")
    else:
        st.dataframe(team, hide_index=True, width="stretch",
                     column_config={"rm": "RM", "peran": "Peran", "dihubungi": "Dihubungi", "deal": "Deal",
                                    "tingkat_deal": st.column_config.NumberColumn("Tingkat deal", format="percent"),
                                    "divalidasi": "Divalidasi ke anchor"})
    log = D.log_rows(5000)
    dec = log["keputusan_rm"].value_counts()
    with st.container(border=True):
        st.metric("Bahan kunjungan disiapkan RM", f"{int(log['halaman'].isin(WORK_PAGES).sum())} paket")
        st.metric("Keputusan RM atas draft AI: setujui / edit / tolak", " / ".join(str(int(dec.get(x, 0))) for x in ["Setujui", "Edit", "Tolak"]))
