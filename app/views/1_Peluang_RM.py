import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components import kontak  # noqa: E402
from app.components.pack import prep_button  # noqa: E402
from app.components.ui import kpi, pct, rupiah, setup  # noqa: E402

setup("Peluang RM", "Langkah 1: pilih nasabah atau calon nasabah. Langkah 2: baca kenapa ia muncul, catat status kontak, lalu siapkan bahan kunjungan.")

pf = D.portfolio()
rms = sorted(pf["rm_id"].unique())
user = st.session_state.get("user", {})
own = user.get("rm_id") if user.get("role") == "rm_wholesale" else None   # an RM sees their own portfolio
rm = st.sidebar.selectbox("RM", rms, index=rms.index(own or D.default_rm()), disabled=own is not None)
mine = pf[pf["rm_id"] == rm].copy()
leads = D.leads_for(rm)
names = D.load("clean", "companies").set_index("company_id")["nama_samaran"]

signals = [c for c in ["pindah_bank", "counterparty_ganti_bank"] if c in mine]
moved = int((mine[signals].sum(axis=1) > 0).sum())
k = kontak.mine(user)
c = st.columns(4)
kpi(c[0], "Nasabah kelolaan", f"{len(mine)} perusahaan", f"{int(mine['status_debitur_awal'].sum())} debitur · {mine['cabang'].iloc[0]}")
kpi(c[1], "Perlu dicek: dana pindah bank", f"{moved} perusahaan", f"{pct(moved / max(len(mine), 1), 0)} portofolio", accent=True)
kpi(c[2], "Calon nasabah dari transaksi", f"{len(leads)} perusahaan", "mitra nasabah Anda di bank lain, 3 bulan terakhir")
kpi(c[3], "Dihubungi / deal (Anda)", f"{k['dihubungi']} / {k['deal']}",
    f"{k['divalidasi']} divalidasi ke anchor" + (f" · tingkat deal {pct(k['tingkat_deal'])}" if k["tingkat_deal"] is not None else ""), accent=True)


def why_customer(r) -> str:
    """Plain-language reason a customer is on the list, most urgent first."""
    out = []
    if r.get("pindah_bank", 0) > 0:
        out.append("dana pindah ke rekening sendiri di bank lain")
    if r.get("counterparty_ganti_bank", 0) > 0:
        out.append("mitranya pindah bank")
    if r.get("counterpart_baru", 0) > 0:
        out.append("ada mitra baru bernilai besar")
    if r["skor_reaktivasi"] >= 0.15:
        out.append("produk trade bisa diaktifkan lagi")
    if r["skor_cross_sell_wholesale"] >= 0.4:
        out.append("peluang produk baru tinggi")
    return ", ".join(out).capitalize() or f"Peluang produk baru {pct(r['skor_cross_sell_wholesale'], 0)}"


mine["alasan"] = mine.apply(why_customer, axis=1)
mine["urgensi"] = mine[[c for c in ["pindah_bank", "counterparty_ganti_bank", "counterpart_baru"] if c in mine]].gt(0).sum(axis=1)
mine = mine.sort_values(["urgensi", "skor_cross_sell_wholesale"], ascending=False).reset_index(drop=True)
mine["debitur"] = mine["status_debitur_awal"].map({1: "Ya", 0: "Belum"})
leads = leads.reset_index(drop=True)
leads["alasan"] = leads.apply(lambda r: (f"{r['sinyal']}; " if r["sinyal"] else "") +
                              f"bertransaksi {rupiah(r['nominal_3bln_rp'])} dengan {r['nasabah_rm_nama']} dalam 3 bulan", axis=1)
status = kontak.read()
status = status[status["akun"] == kontak.account(user)].set_index("entity_id")["status"]
mine["status"] = mine["company_id"].map(status).fillna("Belum dihubungi")
leads["status"] = leads["counterparty_id"].map(status).fillna("Belum dihubungi")

SRC = {"nasabah": (f"Nasabah saya ({len(mine)})", mine, "company_id", "nama_samaran"),
       "lead": (f"Calon nasabah dari transaksi ({len(leads)})", leads, "counterparty_id", "nama")}

# Home page "Siapkan kunjungan ke X" lands here with that customer already picked.
home_pick = st.session_state.pop("peluang_pilih", None)
if home_pick in set(mine["company_id"]):
    st.session_state["peluang_src"], st.session_state["pick_nasabah"] = "nasabah", home_pick


def pick_from_table(kind: str):
    """A row clicked in a table becomes the selection in step 1."""
    rows = st.session_state[f"tbl_{kind}"].selection.rows
    if rows:
        _, df, col, _ = SRC[kind]
        st.session_state["peluang_src"], st.session_state[f"pick_{kind}"] = kind, df.iloc[rows[0]][col]


st.session_state.setdefault("peluang_src", "nasabah")
with st.container(border=True):
    st.markdown("#### 1. Pilih nasabah")
    st.caption("Urutan = paling mendesak dulu: dana pindah bank → mitra ganti bank → mitra baru bernilai besar → peluang produk baru. "
               "Pilih dari daftar, atau klik satu baris di tabel lengkap di bawah.")
    kind = st.segmented_control("Sumber", list(SRC), format_func=lambda x: SRC[x][0], key="peluang_src") or "nasabah"
    label, df, col, name_col = SRC[kind]
    if df.empty:
        st.info("Belum ada data di daftar ini.")
        st.stop()
    by_id = df.set_index(col)
    eid = st.selectbox("Nasabah", by_id.index.tolist(), key=f"pick_{kind}", label_visibility="collapsed",
                       format_func=lambda x: f"{by_id.at[x, name_col]} · {by_id.at[x, 'alasan']} · {by_id.at[x, 'status']}")

with st.expander("Lihat tabel lengkap", icon=":material/table_view:"):
    tab_cust, tab_lead = st.tabs([SRC["nasabah"][0], SRC["lead"][0]])
    with tab_cust:
        st.dataframe(mine[["nama_samaran", "alasan", "sektor", "debitur", "skor_cross_sell_wholesale", "skor_leakage", "status"]],
                     hide_index=True, width="stretch", on_select=lambda: pick_from_table("nasabah"), selection_mode="single-row", key="tbl_nasabah",
                     column_config={"nama_samaran": "Nasabah", "alasan": st.column_config.TextColumn("Kenapa perlu dikunjungi", width="large"),
                                    "sektor": "Sektor", "debitur": "Debitur", "status": "Status kontak",
                                    "skor_cross_sell_wholesale": st.column_config.ProgressColumn("Peluang produk baru (6 bulan)", min_value=0, max_value=1, format="percent"),
                                    "skor_leakage": st.column_config.ProgressColumn("Risiko dana pindah (6 bulan)", min_value=0, max_value=1, format="percent")})
    with tab_lead:
        st.caption("Mitra nasabah Anda yang menyimpan dananya di bank lain. Kontak mereka tidak ditampilkan: dekati lewat nasabah Anda (anchor), "
                   "referral, atau RM di daerahnya.")
        st.dataframe(leads[["nama", "alasan", "kontak_visit", "kanwil", "skor_tipe", "status"]], hide_index=True, width="stretch",
                     on_select=lambda: pick_from_table("lead"), selection_mode="single-row", key="tbl_lead",
                     column_config={"nama": "Calon nasabah", "alasan": st.column_config.TextColumn("Kenapa muncul", width="large"),
                                    "kontak_visit": "Kontak untuk visit", "kanwil": "Kanwil", "status": "Status kontak",
                                    "skor_tipe": st.column_config.ProgressColumn("Peluang jadi nasabah (6 bulan)", min_value=0, max_value=1, format="percent")})

st.markdown(f"#### 2. Persiapan kunjungan: {names.get(eid, eid)}")
r = by_id.loc[eid]
if kind == "nasabah":
    st.markdown(f"**Kenapa:** {r['alasan']}.  \n{r['sektor']} · {r['provinsi']} · debitur: {r['debitur']}  \n"
                f"Peluang produk baru {pct(r['skor_cross_sell_wholesale'], 0)} · risiko dana pindah {pct(r['skor_leakage'], 0)} (dalam 6 bulan)")
else:
    st.markdown(f"**Kenapa:** {r['alasan']}.  \n{r['sektor']} · {r['kc_lokasi']} · {r['kanwil']}  \n"
                f"**Kontak untuk visit:** {r['kontak_visit']}  \nPeluang jadi nasabah dalam 6 bulan: {pct(r['skor_tipe'], 0)}")
kontak.widget(user, eid, "perusahaan" if kind == "lead" else "nasabah_wholesale", lead=kind == "lead")
prep_button(eid, "Peluang RM", f"rm_{eid}")
