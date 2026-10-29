import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from app.components.ui import GREEN, ORANGE, PLOTLY, RED, TEAL, kpi, pct, rupiah, setup  # noqa: E402
from src.impact import profit as P  # noqa: E402

setup("Profit dan Potential Loss", "Berapa nasabah yang perlu dihubungi agar profit bersih paling besar: "
      "titik di mana jarak antara pendapatan dan biaya kontak paling lebar.")

ENGINES = {"Cross-sell wholesale": ("wholesale_cross_sell_wholesale", "perusahaan"), "Akuisisi prospek perusahaan": ("akuisisi_perusahaan", "perusahaan"),
           "Akuisisi semua prospek": ("akuisisi", "calon"), "NBO ritel": ("nbo", "penawaran")}
name = st.sidebar.selectbox("Program", list(ENGINES))
eng, unit = ENGINES[name]
a = P.assumptions()
st.sidebar.markdown("**Asumsi (bisa diubah)**")
ov = {"biaya_kunjungan_rm_wholesale": st.sidebar.slider("Biaya kunjungan RM (Rp)", 250_000, 2_000_000, int(a["biaya_kunjungan_rm_wholesale"]), 50_000),
      "biaya_kontak_ritel": st.sidebar.slider("Biaya kontak ritel (Rp)", 5_000, 50_000, int(a["biaya_kontak_ritel"]), 1_000),
      "spread_dana": st.sidebar.slider("Spread dana", 0.005, 0.04, float(a["spread_dana"]), 0.005),
      "porsi_wallet_tahun_pertama": st.sidebar.slider("Porsi wallet tahun pertama", 0.1, 1.0, float(a["porsi_wallet_tahun_pertama"]), 0.1)}
sk = st.sidebar.radio("Skenario", ["konservatif", "moderat", "optimis"], index=1)
mk = st.sidebar.radio("Suku bunga", ["turun", "tetap", "naik"], index=1)
kw = dict(skenario=a[f"skenario_{sk}"], makro=a[f"pengali_makro_bunga_{mk}"], overrides=ov)


def num(x) -> str:
    return f"{x:,.0f}".replace(",", ".")


@st.cache_data
def cum(eng: str, score: str, skenario: float, makro: float, overrides: dict):
    return P.cumulative(eng, score, skenario, makro, overrides)


mod = cum(eng, "nilai_harapan", **kw)
base = cum(eng, "skor_baseline", **kw)
bm, bb = mod[mod["terbaik"]].iloc[0], base[base["terbaik"]].iloc[0]
n_best = int(bm["dihubungi"])

c = st.columns(4)
kpi(c[0], "Jumlah ideal yang dihubungi", f"{num(n_best)} {unit}", f"titik profit maksimal · cara lama {num(bb['dihubungi'])} {unit}", accent=True)
kpi(c[1], "Profit bersih maksimal", rupiah(bm["profit_bersih"]), f"cara lama maksimal {rupiah(bb['profit_bersih'])}")
kpi(c[2], "Perkiraan konversi", f"{num(bm['konversi'])} {unit}", f"{pct(bm['konversi'] / max(n_best, 1))} dari yang dihubungi")
kpi(c[3], "Tambahan profit vs cara lama", rupiah(bm["profit_bersih"] - bb["profit_bersih"]), "pada data periode uji", accent=True)

st.markdown("### Pendapatan vs biaya kontak: di mana jaraknya paling lebar?")
fig = go.Figure()
fig.add_scatter(x=mod["dihubungi"], y=mod["biaya"], name="Biaya kontak", line=dict(color=RED, width=2))
fig.add_scatter(x=mod["dihubungi"], y=mod["pendapatan_kotor"], name="Pendapatan (urutan model)", line=dict(color=GREEN, width=3),
                fill="tonexty", fillcolor="rgba(46,125,50,0.10)")
fig.add_scatter(x=base["dihubungi"], y=base["pendapatan_kotor"], name="Pendapatan (cara lama)", line=dict(color=ORANGE, width=2, dash="dot"))
fig.add_shape(type="line", x0=n_best, x1=n_best, y0=bm["biaya"], y1=bm["pendapatan_kotor"], line=dict(color=TEAL, width=4))
fig.add_scatter(x=[n_best, n_best], y=[bm["biaya"], bm["pendapatan_kotor"]], mode="markers", marker=dict(color=TEAL, size=11),
                name="Gap terjauh", hoverinfo="skip")
fig.add_annotation(x=n_best, y=bm["pendapatan_kotor"], ax=60, ay=-50, showarrow=True, arrowcolor=TEAL, align="left",
                   bgcolor="white", bordercolor=TEAL, font=dict(color=TEAL),
                   text=f"<b>Hubungi {num(n_best)} teratas</b><br>Profit bersih {rupiah(bm['profit_bersih'])}")
fig.update_layout(**PLOTLY, height=420, yaxis_title="Rupiah (kumulatif)", xaxis_title=f"Jumlah {unit} yang dihubungi (urut dari nilai tertinggi)",
                  legend=dict(orientation="h", y=-0.2))
st.plotly_chart(fig, width="stretch")
st.caption(f"Garis hijau = pendapatan bila {unit} teratas versi model dihubungi; garis merah = biaya kontaknya. "
           f"Garis teal tegak = jarak terlebar (profit bersih maksimal). Setelah titik itu, setiap kontak tambahan biayanya lebih besar dari pendapatannya.")

st.markdown("### Coba jumlah lain")
n = st.slider(f"Jumlah {unit} yang dihubungi", 1, int(mod["dihubungi"].max()), n_best)
ev_m, ev_b = P.evaluate(eng, n, "nilai_harapan", **kw), P.evaluate(eng, n, "skor_baseline", **kw)
c = st.columns(4)
kpi(c[0], "Profit bersih (model)", rupiah(ev_m["profit_bersih"]), f"cara lama {rupiah(ev_b['profit_bersih'])}")
kpi(c[1], "Konversi", f"{num(ev_m['konversi'])} {unit}", f"cara lama {num(ev_b['konversi'])} {unit}")
kpi(c[2], "Rugi: usaha sia-sia", rupiah(ev_m["rugi_usaha_sia_sia"]), f"cara lama {rupiah(ev_b['rugi_usaha_sia_sia'])}", accent=True)
kpi(c[3], "Rugi: peluang terlewat", rupiah(ev_m["rugi_peluang_terlewat"]), f"cara lama {rupiah(ev_b['rugi_peluang_terlewat'])}", accent=True)

st.markdown("### Dari pendapatan ke profit bersih")
wf = go.Figure(go.Waterfall(x=["Pendapatan kotor", "Biaya kontak", "Profit bersih"], measure=["absolute", "relative", "total"],
                            y=[ev_m["pendapatan_kotor"], -ev_m["biaya"], 0], increasing=dict(marker_color=GREEN),
                            decreasing=dict(marker_color=RED), totals=dict(marker_color=TEAL)))
wf.update_layout(**PLOTLY, height=320, yaxis_title="Rp")
st.plotly_chart(wf, width="stretch")
ms = P.mis_selling_prevented()
st.markdown(f"**Salah jual yang dicegah guardrail**: {ms['kasus_diblokir']} rekomendasi diblokir x {rupiah(a['biaya_salah_jual'])} = **{rupiah(ms['rugi_dicegah'])}** (dari log audit).")
st.markdown("**Non-finansial**: waktu persiapan kunjungan lebih singkat (paket H-1 otomatis), alasan rekomendasi terstandar, risiko salah jual berkurang, "
            "dan visibilitas dana ekosistem yang mengalir ke bank lain.")
st.caption("Urutan model = nilai harapan (peluang terkalibrasi x nilai produk - biaya kontak). Cara lama = aturan bisnis yang dipakai RM sekarang. "
           "Semua angka simulasi dari data sintetis dan asumsi di docs/asumsi_f12.csv.")
