"""Write docs/Hasil_Model.md from the latest run (outputs/model/*.csv), so the numbers in the
slides always match the trained models."""
from datetime import date

import pandas as pd

from src.config import ROOT, path

NAMES = {
    "akuisisi": "Akuisisi (semua prospek)",
    "akuisisi_perusahaan": "Akuisisi: prospek perusahaan (daftar RM Commercial)",
    "akuisisi_pedagang": "Akuisisi: pedagang (lewat program anchor)",
    "akuisisi_karyawan": "Akuisisi: karyawan (lewat Payroll Korporasi)",
    "wholesale_cross_sell_wholesale": "Wholesale: cross-sell produk baru",
    "wholesale_non_debitur_ke_debitur": "Wholesale: non-debitur ke debitur",
    "wholesale_reaktivasi": "Wholesale: reaktivasi produk trade",
    "wholesale_leakage": "Wholesale: leakage (dana pindah ke rekening sendiri di bank lain)",
    "nbo": "NBO: cross-sell produk ritel",
}
TEST = {"akuisisi": "fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17",
        "wholesale": "fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17",
        "nbo": "fitur bulan 16, label bulan 17"}
TRAIN = {"akuisisi": "fitur bulan 1-5, label bulan 6-11", "wholesale": "fitur bulan 1-5, label bulan 6-11",
         "nbo": "fitur bulan 13-15, label bulan 14-16 (negative sampling 15%)"}


BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def tanggal() -> str:
    d = date.today()
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def pct(x):
    return f"{x:.1%}".replace(".", ",") if pd.notna(x) else "-"


def num(x, d=3):
    return f"{x:.{d}f}".replace(".", ",") if pd.notna(x) else "-"


def ribu(x):
    return f"{int(x):,}".replace(",", ".")


def table(g: pd.DataFrame) -> str:
    topcol = next(c for c in g.columns if c.startswith("precision@") and c.endswith("%"))
    lines = [f"| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | {topcol.replace('precision', 'Precision')} | Lift desil 1 | F1 | Champion |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for _, r in g.iterrows():
        lines.append(f"| {r['model']} | {num(r['pr_auc_validasi'])} | {num(r['roc_auc'])} | {num(r['pr_auc'])} | {pct(r[topcol])} | "
                     f"{num(r['lift_desil_1'], 2)}x | {num(r['f1'])} | {'**ya**' if r['champion'] == 1 else ''} |")
    return "\n".join(lines)


def ci(r, m: str) -> str:
    mark = "ya" if r[f"{m}_signifikan"] else "**tidak**"
    return f"{num(r[f'{m}_selisih'])} [{num(r[f'{m}_ci_bawah'])}; {num(r[f'{m}_ci_atas'])}] | {mark}"


def significance_section() -> list[str]:
    """Bootstrap CIs (champion vs baseline, graph ablation), oversampling vs class weights, calibration."""
    out = []
    f = path("outputs") / "model" / "signifikansi.csv"
    if f.exists():
        sig = pd.read_csv(f)
        out += ["## Uji signifikansi (paired bootstrap, 95%)", "",
                "Baris test di-resample 1.000 kali (NBO: 200 kali, per nasabah), kedua model dinilai pada sampel yang sama. "
                "Interval yang tidak memuat 0 berarti selisihnya bukan kebetulan.", ""]
        for test, title in [("Champion vs baseline bisnis", "Champion vs baseline bisnis"),
                            ("Ablation: LightGBM + graph vs tanpa graph", "Ablation graph: LightGBM + graph vs LightGBM tanpa graph")]:
            g = sig[sig["uji"] == test]
            if g.empty:
                continue
            out += [f"**{title}**", "", "| Mesin | Selisih ROC-AUC [CI 95%] | Signifikan | Selisih PR-AUC [CI 95%] | Signifikan |",
                    "| --- | --- | --- | --- | --- |"]
            out += [f"| {NAMES.get(r['mesin'], r['mesin'])} | {ci(r, 'roc_auc')} | {ci(r, 'pr_auc')} |" for _, r in g.iterrows()]
            out.append("")
    m = pd.read_csv(path("outputs") / "model" / "ringkasan_model.csv")
    ov = m[m["model"].isin(["LightGBM + graph", "LightGBM + graph (oversampling)"])]
    if ov["model"].nunique() == 2:
        p = ov.pivot_table(index="mesin", columns="model", values=["pr_auc_validasi", "pr_auc", "roc_auc"], sort=False)
        out += ["## Data tidak seimbang: class weights vs oversampling", "",
                "Grill me Q23 dan PRD: class_weight atau random oversampling, hanya di data train, tanpa SMOTE. Keduanya diuji dengan parameter LightGBM yang sama; yang dipakai adalah yang menang di validasi.", "",
                "| Mesin | PR-AUC validasi (class weights) | PR-AUC validasi (oversampling) | PR-AUC test (class weights) | PR-AUC test (oversampling) |",
                "| --- | --- | --- | --- | --- |"]
        for eng, r in p.iterrows():
            out.append(f"| {NAMES.get(eng, eng)} | {num(r[('pr_auc_validasi', 'LightGBM + graph')])} | "
                       f"{num(r[('pr_auc_validasi', 'LightGBM + graph (oversampling)')])} | {num(r[('pr_auc', 'LightGBM + graph')])} | "
                       f"{num(r[('pr_auc', 'LightGBM + graph (oversampling)')])} |")
        out.append("")
    f = path("outputs") / "model" / "kalibrasi.csv"
    if f.exists():
        cal = pd.read_csv(f)
        e = cal.groupby("mesin", sort=False)["ece"].first()
        out += ["## Kalibrasi peluang", "",
                "Ranking nilai harapan (peluang x nilai - biaya) hanya benar bila peluangnya terkalibrasi. "
                "ECE = rata-rata selisih antara peluang prediksi dan konversi aktual per desil (0 = sempurna). Grafik di halaman Model dan Monitoring.", "",
                "| Mesin | ECE |", "| --- | --- |"] + [f"| {NAMES.get(k, k)} | {num(v)} |" for k, v in e.items()] + [""]
    return out


def write() -> str:
    m = pd.read_csv(path("outputs") / "model" / "ringkasan_model.csv")
    shap = pd.read_csv(path("outputs") / "model" / "shap_porsi_graph.csv").set_index("mesin")
    topk = pd.read_csv(path("outputs") / "model" / "nbo_topk.csv")
    fair = pd.read_csv(path("outputs") / "model" / "fairness.csv")
    clean = pd.read_csv(path("outputs") / "cleaning_report.csv") if (path("outputs") / "cleaning_report.csv").exists() else None
    out = [f"# Hasil Model — RM Copilot Value Chain", "",
           f"Dibuat otomatis dari run terakhir pipeline (`python -m pipelines.run_offline`), {tanggal()}. "
           "Semua data sintetis; angka adalah hasil simulasi, bukan performa di data Bank.", "",
           "## Cara membaca", "",
           "- **Walk-forward**: model dilatih di jendela lama dan diuji di jendela yang lebih baru, sehingga tidak ada data masa depan yang bocor.",
           "- **PR-AUC validasi**: dihitung di 25% data jendela train yang disisihkan. Champion dipilih dari angka ini, **tidak** dari test.",
           "- **Test**: jendela terbaru yang tidak pernah dipakai melatih atau memilih model.",
           "- **Baseline bisnis**: cara kerja RM tanpa sistem (prospek dengan nominal terbesar, produk terpopuler, dan sejenisnya).",
           "- **Lift desil 1**: berapa kali lebih banyak konversi di 10% teratas dibanding memilih acak.", ""]

    out += ["## Ringkasan", "", "| Mesin | Champion | ROC-AUC test | Baseline | PR-AUC test | Baseline | Porsi pengaruh graph (SHAP) |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for eng, g in m.groupby("mesin", sort=False):
        ch, bl = g[g["champion"] == 1].iloc[0], g[g["model"] == "Baseline bisnis"].iloc[0]
        sg = shap["porsi_graph"].get(eng) if eng in shap.index else None
        out.append(f"| {NAMES.get(eng, eng)} | {ch['model']} | {num(ch['roc_auc'])} | {num(bl['roc_auc'])} | {num(ch['pr_auc'])} | "
                   f"{num(bl['pr_auc'])} | {pct(sg) if sg is not None else '-'} |")
    out.append("")

    for eng, g in m.groupby("mesin", sort=False):
        fam = "nbo" if eng == "nbo" else ("akuisisi" if eng.startswith("akuisisi") else "wholesale")
        r0 = g.iloc[0]
        ch = g[g["champion"] == 1].iloc[0]
        bl = g[g["model"] == "Baseline bisnis"].iloc[0]
        out += [f"## {NAMES.get(eng, eng)}", "",
                f"- Train: {TRAIN[fam]}; {ribu(r0['n_train'])} baris, {ribu(r0['positif_train'])} positif.",
                f"- Test: {TEST[fam]}; {ribu(r0['n_test'])} baris, {ribu(r0['positif_test'])} positif "
                f"(base rate {pct(r0['positif_test'] / r0['n_test'])}).",
                f"- Champion: **{ch['model']}**, PR-AUC validasi tertinggi ({num(ch['pr_auc_validasi'])}). "
                + (f"Di test: ROC-AUC {num(ch['roc_auc'])} vs baseline {num(bl['roc_auc'])}, PR-AUC {num(ch['pr_auc'])} vs {num(bl['pr_auc'])}."
                   if ch["model"] != "Baseline bisnis" else
                   "Aturan bisnis menang di validasi, jadi sistem memakai aturan, bukan ML."), "", table(g), ""]
        if eng == "nbo":
            out += ["Metrik per nasabah (nasabah yang benar-benar membeli di bulan test):", "",
                    "| Model | Hit@1 | Recall@1 | Hit@3 | Recall@3 |", "| --- | --- | --- | --- | --- |"]
            for _, r in topk.iterrows():
                out.append(f"| {r['model']} | {pct(r['precision@1'])} | {pct(r['recall@1'])} | {pct(r['precision@3'])} | {pct(r['recall@3'])} |")
            out.append("")

    out += significance_section()

    out += ["## Fairness", "",
            "Disparate impact = tingkat rekomendasi kelompok terendah dibagi tertinggi (tanda bila di bawah 0,8). "
            "Equal opportunity = recall kelompok terendah dibagi tertinggi (apakah pembeli sungguhan di setiap kelompok sama-sama ditemukan). "
            "Rasio base rate menunjukkan seberapa besar perbedaan itu memang ada di data.", "",
            "| Mesin | Atribut | Disparate impact | Equal opportunity | Rasio base rate |", "| --- | --- | --- | --- | --- |"]
    for (eng, att), g in fair.groupby(["mesin", "atribut"], sort=False):
        r = g.iloc[0]
        out.append(f"| {eng} | {att} | {num(r['disparate_impact_atribut'], 2)} | {num(r['equal_opportunity_atribut'], 2)} | {num(r['rasio_base_rate_atribut'], 2)} |")
    out += ["", "Jenis kelamin tidak pernah dipakai sebagai fitur; selisih berasal dari fitur yang berkorelasi (penghasilan, pekerjaan). "
            "Nasabah 25 tahun ke bawah jarang direkomendasikan karena syarat produk (kartu kredit 21+ dan penghasilan minimal Rp3 juta). "
            "Untuk akuisisi, aplikasi meranking prospek di dalam tipenya, sehingga perusahaan tidak kalah oleh karyawan yang base rate-nya lebih tinggi.", ""]

    if clean is not None:
        out += ["## Pembersihan data (EDA)", "", "| File | Kolom | Baris | Sama dengan data asli | Masih kosong |", "| --- | --- | --- | --- | --- |"]
        for _, r in clean.iterrows():
            out.append(f"| {r['file']} | {r['kolom']} | {ribu(r['baris'])} | {pct(r['sama_dengan_asli'])} | {pct(r['masih_kosong'])} |")
        out.append("")

    out += ["## Catatan metodologi (pitfall yang ditemukan dan diperbaiki)", "",
            "| Masalah | Gejala | Perbaikan |", "| --- | --- | --- |",
            "| Koordinat embedding FastRP tidak sejajar antar jendela | Model yang memakai embedding mentah turun saat diuji di jendela berikutnya | Embedding mentah diganti kemiripan di dalam satu jendela (mirip nasabah Bank, mirip debitur); NBO memakai kemiripan nasabah-produk |",
            "| Fitur kumulatif bergeser antar jendela | Bulan aktif 5 vs 11, nominal total membesar; skor Logistic Regression jenuh (AUC 0,500) | Semua fitur aktivitas memakai 5 bulan terakhir yang sama panjang |",
            "| Fitur hampir konstan di train | Bulan THR hanya ada di jendela train untuk karyawan | Nilai standar di Logistic Regression dipotong ke rentang -5 sampai 5 |",
            "| Prospek perusahaan kalah oleh karyawan di peringkat gabungan | Hampir tidak ada perusahaan di 10% teratas | Peringkat dan champion per tipe prospek |",
            "| Batas sinyal prospek perusahaan | Yang terlihat bank hanya transaksi dengan nasabah Bank; volume itu sudah ditangkap baseline nominal | Dilaporkan jujur; nilai tambah sistem untuk perusahaan ada di sinyal F19, jangkauan dua langkah, dan konteks |",
            "| Pemilihan model dari test | Risiko data snooping | Champion dipilih dari PR-AUC validasi; test hanya untuk laporan |",
            "| Penjelasan 'nasabah mirip' NBO lemah | Median 0% dari 50 tetangga graph memegang produk yang direkomendasikan (lift rata-rata 0,34x) | Kalimat tetangga hanya ditampilkan bila lift >= 1,5x (sekitar 9% rekomendasi); selebihnya alasan dari SHAP |", ""]
    text = "\n".join(out)
    dst = ROOT / "docs" / "Hasil_Model.md"
    dst.write_text(text, encoding="utf-8")
    return str(dst)
