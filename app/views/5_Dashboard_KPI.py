import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components.ui import PLOTLY, kpi, pct, setup  # noqa: E402

setup("KPI Model", "Tata kelola: presisi daftar teratas tiap mesin dibanding baseline, dan sebaran rekomendasi.")

m = D.report("ringkasan_model.csv")
ch = m[m["champion"] == 1].set_index("mesin")
bl = m[m["model"] == "Baseline bisnis"].set_index("mesin")
c = st.columns(4)
for col, eng, title in [(c[0], "akuisisi", "Akuisisi"), (c[1], "wholesale_cross_sell_wholesale", "Cross-sell wholesale"),
                        (c[2], "wholesale_leakage", "Leakage"), (c[3], "nbo", "NBO ritel")]:
    top = "precision@1%" if eng == "nbo" else "precision@10%"
    kpi(col, f"{title}: presisi daftar teratas", pct(ch.loc[eng, top]), f"baseline {pct(bl.loc[eng, top])}", accent=eng == "nbo")

st.markdown("### Distribusi rekomendasi NBO (top 3 per nasabah, bulan test)")
s = D.load("scores", "nbo_test").sort_values("skor", ascending=False)
top3 = s.groupby("person_id").head(3)
dist = top3[top3["skor"] >= top3["skor"].quantile(0.9)]["produk"].astype(str).value_counts().reset_index()
dist.columns = ["produk", "jumlah"]
fig = px.bar(dist, x="jumlah", y="produk", orientation="h")
fig.update_layout(**PLOTLY, height=360, yaxis=dict(categoryorder="total ascending", title=""), xaxis_title="Rekomendasi (10% skor tertinggi)")
st.plotly_chart(fig, width="stretch")

c1, c2 = st.columns(2)
with c1:
    st.markdown("### Top 10 nasabah (NBO)")
    st.dataframe(top3.drop_duplicates("person_id").head(10)[["person_id", "produk", "skor"]].round(3), hide_index=True, width="stretch")
with c2:
    st.markdown("### Top 10 prospek perusahaan")
    p = D.prospects()
    st.dataframe(p[p["tipe_prospek"] == "perusahaan"].sort_values("peringkat_dalam_tipe").head(10)[["entity_id", "nama", "skor_tipe"]].round(3),
                 hide_index=True, width="stretch")
