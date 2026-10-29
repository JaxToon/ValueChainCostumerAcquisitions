import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app.components import data as D  # noqa: E402
from app.components import kontak  # noqa: E402
from app.components.ui import kpi, pct, rupiah, setup  # noqa: E402

user = st.session_state.get("user", {})
rm = user.get("rm_id") or D.default_rm()
setup(f"Selamat datang, {user.get('nama', 'RM')}", f"Portofolio {rm}. Mulai dari rencana kerja di bawah; klik baris mana pun untuk langsung menyiapkan kunjungan.")

pf = D.portfolio()
mine = pf[pf["rm_id"] == rm].copy()
leads = D.leads_for(rm)
signals = [c for c in ["pindah_bank", "counterparty_ganti_bank"] if c in mine]
at_risk = mine[mine[signals].sum(axis=1) > 0].sort_values("skor_cross_sell_wholesale", ascending=False)   # same order as Peluang RM
top = mine.sort_values("skor_cross_sell_wholesale", ascending=False)

k = kontak.mine(user)
c = st.columns(4)
kpi(c[0], "Nasabah kelolaan", f"{len(mine)} perusahaan", f"{int(mine['status_debitur_awal'].sum())} debitur · {len(mine) - int(mine['status_debitur_awal'].sum())} belum debitur")
kpi(c[1], "Perlu dicek: dana pindah bank", f"{len(at_risk)} perusahaan",
    f"{pct(len(at_risk) / max(len(mine), 1), 0)} portofolio · nasabah atau mitranya memindahkan dana", accent=True)
kpi(c[2], "Sudah Anda hubungi", f"{k['dihubungi']} perusahaan",
    f"target: {len(at_risk)} dana pindah + {len(leads)} calon dari transaksi")
kpi(c[3], "Deal", f"{k['deal']} perusahaan",
    (f"tingkat deal {pct(k['tingkat_deal'])}" if k["tingkat_deal"] is not None else "belum ada yang dihubungi")
    + f" · rata-rata peluang produk baru {pct(mine['skor_cross_sell_wholesale'].mean(), 0)}", accent=True)
st.caption("Dihubungi dan deal dicatat lewat 'Status kontak' di halaman Peluang RM. Peluang produk baru = perkiraan kemungkinan "
           "nasabah mengambil produk wholesale baru dalam 6 bulan ke depan (0–100%).")

def go_prepare(company_id: str):
    st.session_state["peluang_pilih"] = company_id
    st.switch_page("views/1_Peluang_RM.py")


st.subheader("Rencana kerja hari ini")
with st.container(border=True):
    first = at_risk.iloc[0] if len(at_risk) else top.iloc[0]
    st.markdown(f"**1. Amankan dana nasabah.** {len(at_risk)} nasabah memindahkan dana atau mitranya pindah bank. "
                f"Mulai dari **{first['nama_samaran']}** ({first['sektor']}).")
    if st.button(f"Siapkan kunjungan ke {first['nama_samaran']}", key="step1", type="primary", icon=":material/description:"):
        go_prepare(first["company_id"])
    st.markdown(f"**2. Tawarkan produk baru.** Peluang tertinggi: **{top.iloc[0]['nama_samaran']}** "
                f"({top.iloc[0]['skor_cross_sell_wholesale']:.0%} peluang produk baru).")
    if st.button(f"Siapkan kunjungan ke {top.iloc[0]['nama_samaran']}", key="step2", icon=":material/description:"):
        go_prepare(top.iloc[0]["company_id"])
    st.markdown(f"**3. Validasi calon nasabah.** {len(leads)} mitra nasabah Anda masih di bank lain. "
                "Tandai mana yang sudah dicek bersama nasabah Anda (anchor).")
    st.page_link("views/1_Peluang_RM.py", label="Buka daftar calon nasabah", icon=":material/arrow_forward:")

left, right = st.columns(2, gap="large")
with left:
    st.subheader("Nasabah yang perlu dikunjungi")
    view = top.head(8)
    ev = st.dataframe(view[["nama_samaran", "sektor", "skor_cross_sell_wholesale", "skor_leakage"]], hide_index=True, width="stretch",
                      on_select="rerun", selection_mode="single-row", key="home_nasabah",
                      column_config={"nama_samaran": "Nasabah", "sektor": "Sektor",
                                     "skor_cross_sell_wholesale": st.column_config.ProgressColumn("Peluang produk baru", min_value=0, max_value=1, format="percent"),
                                     "skor_leakage": st.column_config.ProgressColumn("Risiko dana pindah", min_value=0, max_value=1, format="percent")})
    if ev.selection.rows:
        go_prepare(view.iloc[ev.selection.rows[0]]["company_id"])
with right:
    st.subheader("Calon nasabah dari transaksi")
    lv = leads.head(8).copy()
    lv["nominal"] = lv["nominal_3bln_rp"].map(rupiah)
    st.dataframe(lv[["nama", "nasabah_rm_nama", "nominal", "kontak_visit"]], hide_index=True, width="stretch",
                 column_config={"nama": "Calon nasabah", "nasabah_rm_nama": "Terhubung dengan", "nominal": "Nominal 3 bulan",
                                "kontak_visit": "Kontak untuk visit"})
    st.caption("Kontak calon nasabah tidak ditampilkan; dekati lewat nasabah Anda, referral, atau RM di daerahnya.")
    st.page_link("views/4_Ekosistem.py", label=f"Lihat semua mitra anchor {D.anchor_showcase()}", icon=":material/hub:")
