"""Load the sourced reference tables (reference/) and the team's assumptions (config.yaml)."""
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference"

AGE_BANDS = ["15-17", "18-25", "26-35", "36-50", "51-79"]
AGE_EDGES = [15, 18, 26, 36, 51, 80]          # band i = [edge i, edge i+1)
OCCUPATIONS = [
    "Pegawai/Profesional", "Pengusaha/Wiraswasta", "Pensiunan/Purnawirawan",
    "Petani/Peternak/Pekebun/Nelayan", "Pekerjaan Lainnya", "Pelajar/Mahasiswa",
    "Ibu Rumah Tangga", "Tidak/Belum Pernah Bekerja",
]
EARNING = OCCUPATIONS[:5]                       # occupations with their own income
INCOME_BANDS = ["< 500 rb", "500 rb - 1,5 jt", "1,5 - 2,5 jt", "2,5 - 3,5 jt", "> 3,5 jt"]
INCOME_EDGES = [0, 500_000, 1_500_000, 2_500_000, 3_500_000, float("inf")]
NO_INCOME = "Tidak ada kegiatan ekonomi"


@dataclass
class Ref:
    cfg: dict
    pop_prov: pd.DataFrame
    pop_age_sex: pd.DataFrame
    wage_lognormal: pd.DataFrame
    wage_brackets: pd.DataFrame
    wage_age: pd.DataFrame
    sectors: pd.DataFrame
    snlik_profile: pd.DataFrame
    snlik_inclusion: pd.DataFrame
    calendar: pd.DataFrame
    catalog: pd.DataFrame
    product_model: pd.DataFrame
    dyn_products: pd.DataFrame
    rr_age: pd.DataFrame
    rr_income: pd.DataFrame
    corr: pd.DataFrame
    dyn_customers: pd.DataFrame
    santander_extra: pd.DataFrame
    public: pd.DataFrame
    ksei: pd.DataFrame

    def indicator(self, key: str) -> float:
        return float(self.public.set_index("indikator").loc[key, "nilai"])

    def snlik(self, table: str, dim: str) -> pd.Series:
        df = self.snlik_profile if table == "profil" else self.snlik_inclusion
        col = "jumlah_juta" if table == "profil" else "inklusi_persen"
        d = df[df["dimensi"] == dim]
        return pd.Series(d[col].to_numpy(), index=d["kategori"].to_numpy())

    def extra(self, key: str) -> float:
        return float(self.santander_extra.set_index("indikator").loc[key, "nilai"])


def load(config_path: Path) -> Ref:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    r = lambda name, **kw: pd.read_csv(REF / name, **kw)
    return Ref(
        cfg=cfg,
        pop_prov=r("bps_penduduk_provinsi_2026.csv"),
        pop_age_sex=r("bps_penduduk_umur_jk_2025.csv"),
        wage_lognormal=r("bps_upah_lognormal_2025.csv"),
        wage_brackets=r("bps_upah_kelompok_2025.csv"),
        wage_age=r("bps_upah_umur_2025.csv"),
        sectors=r("bps_pekerja_sektor_2025.csv"),
        snlik_profile=r("ojk_snlik_2025_profil.csv"),
        snlik_inclusion=r("ojk_snlik_2025_inklusi.csv"),
        calendar=r("kalender_2025_2026.csv"),
        catalog=r("produk_bank_knowledge.csv"),
        product_model=r("produk_model.csv", keep_default_na=False),
        dyn_products=r("dinamika_produk_santander.csv"),
        rr_age=r("rr_umur_santander.csv"),
        rr_income=r("rr_pendapatan_santander.csv"),
        corr=r("korelasi_produk_santander.csv", index_col=0),
        dyn_customers=r("dinamika_nasabah_santander.csv"),
        santander_extra=r("santander_tambahan.csv"),
        public=r("indikator_publik.csv"),
        ksei=r("ksei_investor_2025.csv"),
    )
