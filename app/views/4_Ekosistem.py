import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import networkx as nx  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components.ui import GREEN, ORANGE, PLOTLY, TEAL, kpi, pct, rupiah, setup  # noqa: E402

setup("Ekosistem Value Chain", "Mitra nasabah (supplier dan buyer), siapa yang sudah Bank, cabang dan kanwil kelolaan, "
      "volume transaksi per bulan, dan close loop.")

comp = D.load("clean", "companies").set_index("company_id")
show = D.anchor_showcase()
user = st.session_state.get("user", {})
if user.get("role") == "rm_wholesale":   # an RM sees the showcase anchor and their own portfolio
    pf = D.portfolio()
    options = [show] + [c for c in pf.loc[pf["rm_id"] == user.get("rm_id"), "company_id"] if c != show]
else:
    options = comp.index[comp["is_anchor"].astype(bool)].tolist()
a = st.sidebar.selectbox("Nasabah / anchor", options, index=options.index(show) if show in options else 0,
                         format_func=lambda x: f"{x} · {comp['nama_samaran'].get(x, x)}{' (showcase)' if x == show else ''}")
g = D.partners(a)
if g.empty:
    st.info("Belum ada transaksi dengan mitra dalam 6 bulan terakhir.")
    st.stop()
flows = D.monthly_flows(a)
other = ~g["sudah_bank"]
info = comp.loc[a]
st.caption(f"{info['nama_samaran']} · {D.sector_names().get(str(info['sektor']), info['sektor'])} · {info['provinsi']} · "
           f"{D.kanwil_map()['kanwil'].get(info['provinsi'], '-')} · {info.get('cabang') or '-'} · RM {info.get('rm_id') or '-'}")

bench = D.anchor_benchmark()
n_bank, n_sup, n_buy = int(g["sudah_bank"].sum()), int((g["peran"] != "Buyer").sum()), int((g["peran"] != "Supplier").sum())
last, avg = flows["close_loop"].iloc[-1], flows["close_loop"].mean()
c = st.columns(5)
kpi(c[0], "Mitra transaksi", f"{len(g)} mitra", f"{n_sup} supplier · {n_buy} buyer · 6 bulan terakhir")
kpi(c[1], "Mitra sudah nasabah Bank", f"{n_bank} dari {len(g)} mitra",
    f"{pct(n_bank / len(g), 0)} · median {bench['jumlah_anchor']} anchor: {pct(bench['porsi_mitra_bank'], 0)}")
kpi(c[2], "Close loop bulan terakhir", pct(last, 0),
    f"nilai transaksi yang tetap di Bank · rata-rata 6 bulan {pct(avg, 0)} · median anchor {pct(bench['close_loop'], 0)}", accent=True)
kpi(c[3], "Nilai transaksi", f"{rupiah(g['nominal_per_bulan'].sum())}/bulan", f"{g['frekuensi_per_bulan'].sum():,.0f} transaksi per bulan".replace(",", "."))
kpi(c[4], "Dana ke mitra di bank lain", f"{rupiah(g.loc[other, 'nominal_per_bulan'].sum())}/bulan",
    f"{int(other.sum())} mitra · potensi dana yang bisa dibawa ke Bank", accent=True)

tab_list, tab_vol, tab_map = st.tabs(["Daftar mitra", "Volume dan close loop (bahan TAP)", "Peta dan funnel"])

with tab_list:
    with st.container(horizontal=True):
        peran = st.pills("Peran", ["Supplier", "Buyer", "Supplier dan buyer"], selection_mode="multi",
                         default=["Supplier", "Buyer", "Supplier dan buyer"], key="eko_peran")
        status = st.segmented_control("Status", ["Semua", "Sudah Bank", "Belum Bank"], default="Semua", key="eko_status")
        kanwil = st.multiselect("Kanwil", sorted(g["kanwil"].dropna().unique()), key="eko_kanwil", placeholder="Semua kanwil")
    v = g[g["peran"].isin(peran or [])]
    if status == "Sudah Bank":
        v = v[v["sudah_bank"]]
    elif status == "Belum Bank":
        v = v[~v["sudah_bank"]]
    if kanwil:
        v = v[v["kanwil"].isin(kanwil)]
    st.dataframe(v[["nama", "peran", "sudah_bank", "kontak_visit", "kc_lokasi", "kanwil", "kc_kelolaan", "sektor",
                    "nominal_per_bulan", "frekuensi_per_bulan", "bulan_aktif"]], hide_index=True, width="stretch",
                 column_config={"nama": "Mitra", "peran": "Peran", "sudah_bank": st.column_config.CheckboxColumn("Sudah Bank"),
                                "kontak_visit": "Kontak untuk visit", "kc_lokasi": "KC di daerah mitra", "kanwil": "Kanwil",
                                "kc_kelolaan": "KC kelolaan", "sektor": "Sektor",
                                "nominal_per_bulan": st.column_config.NumberColumn("Nominal per bulan (Rp)", format="localized"),
                                "frekuensi_per_bulan": st.column_config.NumberColumn("Transaksi per bulan", format="%.1f"),
                                "bulan_aktif": st.column_config.NumberColumn("Bulan aktif (dari 6)")})
    st.caption(f"{len(v)} dari {len(g)} mitra. Supplier = nasabah membayar mitra; buyer = mitra membayar nasabah. "
               "Kontak untuk visit: nasabah Bank -> RM pengelolanya; belum nasabah -> RM di KC daerah mitra, atau Kanwil bila KC itu belum punya RM. "
               "Transfer ke rekening sendiri tidak dihitung. Di data sintetis satu provinsi = satu KC; Kanwil dari provinsi_kanwil.csv.")

with tab_vol:
    channels = {"PEMINDAHBUKUAN": ("Pemindahbukuan (antar rekening Bank)", TEAL), "BI-FAST": ("BI-FAST", ORANGE),
                "SKN": ("SKN", "#5C7C89"), "RTGS": ("RTGS", "#9BB7BF")}
    ch_cols = [col for col in channels if col in flows]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for col in ch_cols:
        fig.add_bar(x=flows["bulan"], y=flows[col] / 1e9, name=channels[col][0], marker_color=channels[col][1], secondary_y=False)
    fig.add_scatter(x=flows["bulan"], y=flows["close_loop"], name="Close loop", mode="lines+markers",
                    line=dict(color=GREEN, width=3), secondary_y=True)
    fig.update_layout(**PLOTLY, barmode="stack", height=380, legend=dict(orientation="h", y=-0.15))
    fig.update_yaxes(title_text="Nominal per bulan (miliar Rp)", secondary_y=False)
    fig.update_yaxes(title_text="Close loop", tickformat=".0%", range=[0, 1], secondary_y=True)
    st.plotly_chart(fig, width="stretch")
    st.caption("Close loop = porsi nilai transaksi dengan mitra yang juga nasabah Bank (dana tetap di Bank). "
               "Volume ditampilkan per jalur transaksi; volume per produk Bank belum tersedia di data.")
    tbl = flows.assign(bulan=flows["bulan"].astype(str).str[:7])
    st.dataframe(tbl, hide_index=True, width="stretch",
                 column_config={**{col: st.column_config.NumberColumn(channels[col][0], format="localized") for col in ch_cols},
                                "close_loop": st.column_config.NumberColumn("Close loop", format="percent"),
                                "jumlah_transaksi": "Jumlah transaksi", "bulan": "Bulan"})
    used = D.products_used(a)
    if len(used):
        st.markdown("**Produk Bank yang pernah dan sedang dipakai**")
        st.dataframe(used, hide_index=True, width="stretch",
                     column_config={"produk": "Produk", "status": "Status", "tanggal_mulai": "Mulai", "tanggal_selesai": "Selesai",
                                    "konteks": "Konteks"})

with tab_map:
    top = g.head(40).set_index("mitra_id")
    G = nx.Graph()
    G.add_node(a)
    for cid in top.index:
        G.add_edge(a, cid)
    pos = nx.spring_layout(G, seed=7, weight=None)
    ex, ey = [], []
    for u, w in G.edges():
        ex += [pos[u][0], pos[w][0], None]
        ey += [pos[u][1], pos[w][1], None]
    fig = go.Figure([go.Scatter(x=ex, y=ey, mode="lines", line=dict(color="#C9D6DA", width=1), hoverinfo="skip")])
    for label, mask, color in [("Nasabah Bank", top["sudah_bank"], TEAL), ("Bank lain (prospek)", ~top["sudah_bank"], ORANGE)]:
        t = top[mask]
        fig.add_trace(go.Scatter(x=[pos[i][0] for i in t.index], y=[pos[i][1] for i in t.index], mode="markers", name=label,
                                 marker=dict(size=10 + 18 * (t["nominal_per_bulan"] / top["nominal_per_bulan"].max()) ** 0.5, color=color),
                                 text=[f"{n}<br>{p} · {rupiah(val)}/bulan" for n, p, val in zip(t["nama"], t["peran"], t["nominal_per_bulan"])],
                                 hoverinfo="text"))
    fig.add_trace(go.Scatter(x=[pos[a][0]], y=[pos[a][1]], mode="markers+text", name="Nasabah", text=[a], textposition="top center",
                             marker=dict(size=28, color=GREEN, symbol="diamond")))
    fig.update_layout(**PLOTLY, height=480, xaxis=dict(visible=False), yaxis=dict(visible=False), legend=dict(orientation="h"))
    st.plotly_chart(fig, width="stretch")
    st.caption("40 mitra terbesar. Ukuran titik = nominal per bulan. Oranye = mitra di bank lain, calon prospek.")

    pr = D.prospects().set_index("entity_id")
    cand = g.loc[other, "mitra_id"]
    cand = cand[cand.isin(pr.index)]
    top10 = pr.groupby("tipe_prospek")["peringkat_dalam_tipe"].transform("max") * 0.1
    hi = int((pr.loc[cand, "peringkat_dalam_tipe"] <= top10.loc[cand]).sum()) if len(cand) else 0
    fun = go.Figure(go.Funnel(y=["Mitra", "Di bank lain", "Terlihat bank (prospek)", "Peluang tinggi (10% teratas)"],
                              x=[len(g), int(other.sum()), len(cand), hi], marker=dict(color=[TEAL, ORANGE, ORANGE, GREEN])))
    fun.update_layout(**PLOTLY, height=320)
    st.plotly_chart(fun, width="stretch")
    st.caption("Status 'divalidasi RM' diisi di halaman Peluang RM.")
