import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components.ui import ORANGE, PLOTLY, TEAL, kpi, pct, setup  # noqa: E402

setup("Model dan Monitoring", "Tata kelola: kualitas model dibanding cara lama, kualitas jawaban AI, fairness, dan drift.")

ENGINE_LABEL = {"akuisisi": "Akuisisi (semua)", "akuisisi_perusahaan": "Prospek perusahaan", "akuisisi_pedagang": "Pedagang",
                "akuisisi_karyawan": "Karyawan", "wholesale_cross_sell_wholesale": "Cross-sell wholesale",
                "wholesale_non_debitur_ke_debitur": "Non-debitur ke debitur", "wholesale_reaktivasi": "Reaktivasi trade",
                "wholesale_leakage": "Leakage", "nbo": "NBO ritel"}


def auc(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


st.markdown("### Ringkasan: apakah model lebih baik dari cara kerja sekarang?")
m0 = D.report("ringkasan_model.csv")
ch, bl = m0[m0["champion"] == 1].set_index("mesin"), m0[m0["model"] == "Baseline bisnis"].set_index("mesin")
log = D.log_rows(5000)
ev_file0 = pathlib.Path(__file__).resolve().parents[2] / "outputs" / "eval" / "deepeval_skor.csv"
ev0 = pd.read_csv(ev_file0) if ev_file0.exists() else None
c = st.columns(4)
kpi(c[0], "NBO: ROC-AUC", auc(ch.loc["nbo", "roc_auc"]), f"cara lama {auc(bl.loc['nbo', 'roc_auc'])}")
kpi(c[1], "Akuisisi: ROC-AUC", auc(ch.loc["akuisisi", "roc_auc"]), f"cara lama {auc(bl.loc['akuisisi', 'roc_auc'])}")
kpi(c[2], "Kualitas jawaban AI (DeepEval)", pct(ev0[ev0["error"].isna()]["lolos"].mean(), 0) if ev0 is not None else "-", "penilaian lolos", accent=True)
kpi(c[3], "Permintaan diblokir guardrail", f"{int(log['status'].str.contains('diblokir').sum())}",
    f"dari {len(log)} permintaan tercatat (termasuk uji)", accent=True)
try:
    sig0 = D.report("signifikansi.csv")
    sig0 = sig0[sig0["uji"] == "Champion vs baseline bisnis"].copy()
    sig0["mesin"] = sig0["mesin"].map(ENGINE_LABEL).fillna(sig0["mesin"])
    sig0["signifikan"] = sig0["roc_auc_signifikan"].map({True: "Ya", False: "Tidak"})
    st.dataframe(sig0[["mesin", "roc_auc_selisih", "signifikan", "model_a"]], hide_index=True, width="stretch",
                 column_config={"mesin": "Mesin", "model_a": "Model terpilih",
                                "roc_auc_selisih": st.column_config.NumberColumn("Selisih ROC-AUC", format="%+.3f"), "signifikan": "Signifikan"})
    st.caption("Paired bootstrap 1.000x di jendela test. Prospek perusahaan setara dengan aturan RM; nilainya ada di data counterpart dan alur kerja.")
except FileNotFoundError:
    st.caption("Uji signifikansi belum dihitung.")
st.divider()

m = D.report("ringkasan_model.csv")
eng = st.sidebar.selectbox("Mesin", m["mesin"].unique().tolist())
g = m[m["mesin"] == eng]
top = "precision@1%" if eng == "nbo" else "precision@10%"
st.markdown("### Perbandingan model (test = jendela terbaru)")
st.dataframe(g[["model", "pr_auc_validasi", "roc_auc", "pr_auc", top, "lift_desil_1", "f1", "champion"]].round(3), hide_index=True, width="stretch",
             column_config={"champion": st.column_config.CheckboxColumn("Champion")})
fig = px.bar(g, x="model", y=["roc_auc", "pr_auc"], barmode="group", color_discrete_sequence=[TEAL, ORANGE])
fig.update_layout(**PLOTLY, height=320, xaxis_title="", yaxis_title="", legend_title="")
st.plotly_chart(fig, width="stretch")

st.markdown("### SHAP global (champion)")
try:
    sh = D.report(f"{eng}_shap_global.csv").head(15)
    fig = px.bar(sh, x="mean_abs_shap", y="fitur", color="kelompok", orientation="h", color_discrete_map={"graph": TEAL, "profil": ORANGE})
    fig.update_layout(**PLOTLY, height=420, yaxis=dict(categoryorder="total ascending", title=""), xaxis_title="Rata-rata |SHAP|")
    st.plotly_chart(fig, width="stretch")
except FileNotFoundError:
    st.caption("SHAP belum dihitung untuk mesin ini.")

st.markdown("### Signifikansi dan kalibrasi")
try:
    sig = D.report("signifikansi.csv")
    sg = sig[sig["mesin"] == eng]
    if len(sg):
        st.dataframe(sg.assign(**{"selisih ROC-AUC [CI 95%]": sg.apply(lambda r: f"{r.roc_auc_selisih:+.3f} [{r.roc_auc_ci_bawah:+.3f}; {r.roc_auc_ci_atas:+.3f}]", axis=1),
                                  "signifikan": sg["roc_auc_signifikan"]})[["uji", "selisih ROC-AUC [CI 95%]", "signifikan"]],
                     hide_index=True, width="stretch")
    cal = D.report("kalibrasi.csv")
    cg = cal[cal["mesin"] == eng]
    if len(cg):
        lim = float(max(cg["prediksi_rata"].max(), cg["aktual"].max())) * 1.05
        fig = px.line(cg, x="prediksi_rata", y="aktual", markers=True, color_discrete_sequence=[TEAL])
        fig.add_scatter(x=[0, lim], y=[0, lim], mode="lines", line=dict(dash="dot", color="#8A94A6"), name="terkalibrasi sempurna")
        fig.update_layout(**PLOTLY, height=320, xaxis_title="Peluang prediksi (rata-rata per desil)", yaxis_title="Konversi aktual",
                          showlegend=False)
        st.plotly_chart(fig, width="stretch")
        st.caption(f"ECE {cg['ece'].iloc[0]:.3f}. Titik dekat garis putus-putus = peluang bisa dipakai langsung untuk nilai harapan rupiah.")
except FileNotFoundError:
    st.caption("Belum ada. Jalankan: python -m pipelines.run_offline --only report")

st.markdown("### Fairness")
f = D.report("fairness.csv")
st.dataframe(f.groupby(["mesin", "atribut"]).agg(disparate_impact=("disparate_impact_atribut", "first"),
                                                 equal_opportunity=("equal_opportunity_atribut", "first"),
                                                 rasio_base_rate=("rasio_base_rate_atribut", "first")).round(2).reset_index(),
             hide_index=True, width="stretch")
st.caption("Di bawah 0,8 diberi tanda. Jenis kelamin tidak dipakai sebagai fitur; selisih dijelaskan di docs/Hasil_Model.md.")

st.markdown("### Kualitas output LLM (DeepEval)")
ev_file = pathlib.Path(__file__).resolve().parents[2] / "outputs" / "eval" / "deepeval_skor.csv"
if ev_file.exists():
    ev = pd.read_csv(ev_file)
    ok = ev[ev["error"].isna()]
    c = st.columns(3)
    c[0].metric("Penilaian lolos", f"{ok['lolos'].mean():.0%}")
    c[1].metric("Kasus", ev["kasus"].nunique())
    c[2].metric("Biaya juri", f"${ev['biaya_usd'].sum():.2f}")
    agg = ok.groupby("metrik").agg(skor_rata=("skor", "mean"), lolos=("lolos", "mean"), ambang=("ambang", "first")).reset_index()
    fig = px.bar(agg, x="skor_rata", y="metrik", orientation="h", color_discrete_sequence=[TEAL], range_x=[0, 1])
    fig.update_layout(**PLOTLY, height=280, yaxis_title="", xaxis_title="Skor rata-rata (0-1)")
    st.plotly_chart(fig, width="stretch")
    st.caption("Generator Gemma 4 E4B lokal, juri gpt-4.1-mini. Rincian per kasus di docs/Hasil_DeepEval.md.")
else:
    st.caption("Belum ada hasil. Jalankan: python -m tests.eval_report")

st.markdown("### Drift fitur akuisisi: jendela 1 vs jendela 2 (PSI)")


def psi(a: pd.Series, b: pd.Series, bins: int = 10) -> float:
    a, b = a.dropna(), b.dropna()
    if a.nunique() < 2:
        return 0.0
    edges = np.unique(np.quantile(a, np.linspace(0, 1, bins + 1)))
    pa = np.histogram(a, edges)[0] / len(a) + 1e-6
    pb = np.histogram(b.clip(edges[0], edges[-1]), edges)[0] / max(len(b), 1) + 1e-6
    return float(((pa - pb) * np.log(pa / pb)).sum())


feat = pd.read_parquet(pathlib.Path(__file__).resolve().parents[2] / "data" / "processed" / "features" / "akuisisi.parquet")
from src.features.acq_features import GRAPH, TABLE  # noqa: E402
cols = [c for c in TABLE + GRAPH if c not in ("sektor",)]
d = pd.DataFrame({"fitur": cols, "psi": [psi(feat.loc[feat["jendela_k"] == 1, c], feat.loc[feat["jendela_k"] == 2, c]) for c in cols]})
d["status"] = np.select([d["psi"] > 0.25, d["psi"] > 0.1], ["Drift besar", "Waspada"], "Stabil")
st.dataframe(d.sort_values("psi", ascending=False).round(3), hide_index=True, width="stretch")
st.caption("PSI > 0,25 = drift besar (perlu retrain/cek fitur); 0,1-0,25 = waspada.")
