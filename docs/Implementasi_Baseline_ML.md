# Implementasi Baseline Model Machine Learning

Dokumen ini menjelaskan bagaimana model machine learning RM Copilot dibangun dari awal: masalah yang diprediksi, data dan pembagian waktu, baseline bisnis, kandidat model, cara memilih model, dan hasilnya. Semua data **sintetis**; angka adalah hasil simulasi, bukan performa di data Bank.

Kode utama: `pipelines/run_offline.py`, `src/features/`, `src/models/train.py`, `src/models/significance.py`. Angka di dokumen ini diambil dari `outputs/model/ringkasan_model.csv` dan `docs/Hasil_Model.md` (dibuat otomatis oleh pipeline).

## 1. Tiga mesin prediksi

| Mesin | Pertanyaan yang dijawab | Satu baris data | Label positif |
|---|---|---|---|
| **Akuisisi** (value chain) | Siapa yang terlihat bertransaksi dengan nasabah Bank dan paling mungkin menjadi nasabah dalam 6 bulan? | satu prospek (perusahaan, pedagang, atau karyawan) per jendela | menjadi nasabah Bank di bulan label |
| **Wholesale** (4 label) | Nasabah Commercial mana yang siap cross-sell, naik jadi debitur, reaktivasi produk trade, atau berisiko memindahkan dana? | satu perusahaan nasabah per jendela | cross-sell, non-debitur → debitur, reaktivasi, leakage |
| **NBO** (ritel) | Produk apa yang paling mungkin dibeli nasabah perorangan bulan depan? | satu pasangan nasabah × produk yang belum dimiliki | membeli produk itu di bulan label (tidak dimiliki 3 bulan sebelumnya) |

Akuisisi juga dilatih terpisah per tipe prospek (perusahaan, pedagang, karyawan), karena RM yang berbeda menangani tipe yang berbeda dan base rate-nya berbeda.

## 2. Pembagian waktu (walk-forward)

Model selalu dilatih di masa lalu dan diuji di masa depan, sehingga tidak ada data masa depan yang bocor ke fitur.

| Mesin | Train (dan validasi) | Test |
|---|---|---|
| Akuisisi, wholesale | fitur bulan 1–5, label bulan 6–11 | fitur bulan 7–11 (graph sampai bulan 11), label bulan 12–17 |
| NBO | fitur bulan 13–15, label bulan 14–16 (negative sampling 15%) | fitur bulan 16, label bulan 17 |

- **Validasi** = 25% data jendela train yang disisihkan (stratified). Model terbaik dipilih dari sini, **tidak pernah dari test**.
- **Panjang lookback sama**: fitur aktivitas memakai 5 bulan terakhir di setiap jendela, supaya fitur kumulatif tidak bergeser antar jendela.
- `tests/test_no_lookahead.py` memastikan fitur tidak memakai bulan label.

## 3. Fitur

| Kelompok | Contoh | Sumber |
|---|---|---|
| Tabel (profil dan transaksi) | tipe prospek, sektor, `log_nominal_total`, jumlah transaksi, bulan aktif, jumlah tetangga, tren nominal 3 bulan | `src/features/acq_features.py`, `wholesale_features.py`, `nbo_features.py` |
| Graph (dari Neo4j GDS) | nominal dengan nasabah Bank, porsi tetangga yang nasabah Bank, porsi Bank dua langkah, PageRank, porsi Bank di komunitas Louvain, kemiripan embedding FastRP ke nasabah Bank | `src/graph/algorithms.py` → `data/processed/graph/` |
| Sinyal F19 | counterpart baru, counterpart ganti bank, dana pindah ke rekening sendiri di bank lain | `src/features/signals.py` |

Embedding FastRP mentah **tidak** dipakai langsung karena koordinatnya tidak sejajar antar jendela waktu. Yang dipakai adalah kemiripan di dalam satu jendela (misalnya kemiripan prospek dengan nasabah Bank). Nama kolom dibersihkan karena LightGBM menolak karakter seperti koma.

## 4. Baseline bisnis

Baseline adalah cara kerja RM tanpa sistem: satu kolom yang langsung dipakai sebagai skor ranking. Semua model harus mengalahkan baseline ini di validasi, bukan hanya mengalahkan pilihan acak.

| Mesin | Baseline (kolom skor) | Artinya |
|---|---|---|
| Akuisisi (semua tipe) | `log_nominal_total` | dahulukan prospek dengan nominal transaksi terbesar yang terlihat |
| Wholesale cross-sell | `jumlah_produk_aktif` | dahulukan nasabah yang sudah memegang banyak produk |
| Wholesale non-debitur → debitur | `log_saldo_rata2` | dahulukan nasabah dengan saldo rata-rata terbesar |
| Wholesale reaktivasi | `bulan_sejak_trade_selesai` | dahulukan berdasarkan lama sejak produk trade terakhir selesai |
| Wholesale leakage | `porsi_ke_rekening_sendiri_bank_lain` | dahulukan nasabah yang paling banyak memindahkan dana ke rekening sendiri di bank lain |
| NBO | `popularitas_produk` | tawarkan produk yang paling banyak dimiliki nasabah lain |

## 5. Kandidat model

Semua kandidat dilatih dengan data dan fitur yang sama (`src/models/train.py`, fungsi `candidates`).

| Kandidat | Pengaturan penting | Kenapa ada |
|---|---|---|
| Logistic Regression | StandardScaler, nilai standar dipotong ±5, `class_weight="balanced"`, C=0,5 | model sederhana dan mudah dijelaskan; pembanding linear |
| Random Forest | 300 pohon, `min_samples_leaf=20`, `class_weight="balanced_subsample"` | non-linear tanpa banyak tuning |
| XGBoost | 400 pohon, kedalaman 5, `scale_pos_weight` | gradient boosting standar industri |
| LightGBM tanpa graph | 400 pohon, hanya fitur tabel | **ablation**: mengukur nilai tambah fitur graph |
| LightGBM + graph | parameter dari Optuna (20–25 percobaan, PR-AUC di holdout train) | model utama yang memakai knowledge graph |
| LightGBM + graph (oversampling) | parameter yang sama, positif di-oversample acak di data train | membandingkan oversampling dengan class weights (grill me Q23) |

**Data tidak seimbang.** Base rate rendah (NBO 0,2%, akuisisi 5,6%). Ditangani hanya di data train: class weights atau random oversampling. SMOTE tidak dipakai karena titik sintetis tidak bermakna di ruang embedding graph. Validasi dan test tetap memakai distribusi asli.

## 6. Cara memilih dan menyiapkan model

1. Semua kandidat dan baseline dinilai dengan **PR-AUC di data validasi** (lebih jujur dari ROC-AUC untuk kelas langka).
2. Nilai tertinggi menjadi **champion**. Bila baseline menang, sistem memakai aturan bisnis, bukan ML. Ini terjadi untuk wholesale non-debitur → debitur.
3. Champion dilatih ulang di seluruh jendela train lalu **dikalibrasi** dengan isotonic regression (5-fold), supaya skornya bisa dibaca sebagai peluang. Peluang terkalibrasi dipakai untuk ranking nilai harapan rupiah (peluang × nilai − biaya) di halaman Profit.
4. Semua model dilaporkan di jendela test: ROC-AUC, PR-AUC, presisi di daftar teratas (10%, NBO 1%), lift desil 1, F1, dan Brier score untuk champion.
5. Penjelasan per prediksi memakai SHAP (`src/explain/shap_explain.py`); fairness dicek per jenis kelamin, kelompok usia, dan provinsi (`src/explain/fairness.py`).

## 7. Hasil di jendela test

Presisi daftar teratas = persentase yang benar-benar konversi di 10% teratas (NBO: 1% teratas).

| Mesin | Champion | ROC-AUC champion | ROC-AUC baseline | Presisi teratas champion | Presisi teratas baseline | Base rate |
|---|---|---|---|---|---|---|
| Akuisisi (semua) | LightGBM + graph | 0,725 | 0,529 | 19,1% | 8,8% | 5,6% |
| Prospek perusahaan | Logistic Regression | 0,694 | 0,683 | 12,0% | 11,9% | 4,1% |
| Pedagang | Logistic Regression | 0,747 | 0,488 | 22,7% | 4,9% | 4,9% |
| Karyawan | LightGBM + graph (oversampling) | 0,707 | 0,524 | 23,8% | 9,1% | 7,8% |
| Cross-sell wholesale | Logistic Regression | 0,811 | 0,747 | 43,5% | 36,9% | 10,6% |
| Non-debitur → debitur | Baseline bisnis | 0,692 | 0,692 | 15,6% | 15,6% | 7,6% |
| Reaktivasi trade | Logistic Regression | 0,646 | 0,457 | 20,5% | 11,5% | 14,2% |
| Leakage | Logistic Regression | 0,707 | 0,661 | 12,2% | 7,8% | 4,7% |
| NBO ritel | LightGBM + graph | 0,946 | 0,808 | 7,5% | 0,4% | 0,2% |

Untuk NBO, metrik per nasabah lebih mudah dipahami RM: produk pertama yang direkomendasikan benar **71%** (baseline produk terpopuler 27%), dan 3 produk teratas menangkap 93% pembelian.

### Apakah selisihnya bukan kebetulan?

`src/models/significance.py` menjalankan **paired bootstrap** 1.000 kali (NBO 200 kali per nasabah) di jendela test. Ringkasannya:

- Champion lebih baik dari baseline secara signifikan di akuisisi, pedagang, karyawan, cross-sell, reaktivasi, dan NBO.
- **Prospek perusahaan tidak signifikan**: +0,011 ROC-AUC, CI 95% [−0,001; 0,023]. Aturan RM "nominal terbesar" sudah sama baiknya. Nilai sistem untuk RM Commercial ada di data counterpart (sinyal F19), jangkauan dua langkah di graph, dan paket kunjungan, bukan di ranking ML.
- Leakage signifikan di PR-AUC tapi tidak di ROC-AUC.
- **Ablation graph** (LightGBM + graph vs tanpa graph) signifikan di 7 dari 9 mesin, termasuk prospek perusahaan (+0,059). Ini bukti utama bahwa knowledge graph memberi nilai tambah.

### Kalibrasi

Expected Calibration Error per mesin 0,006–0,041 (0 = sempurna), jadi peluang bisa dipakai langsung untuk nilai harapan rupiah. Grafik reliability ada di halaman Model dan Monitoring.

## 8. Masalah yang ditemukan saat membangun baseline

| Masalah | Gejala | Perbaikan |
|---|---|---|
| Embedding FastRP tidak sejajar antar jendela | model dengan embedding mentah turun di jendela berikutnya | ganti dengan kemiripan di dalam satu jendela |
| Fitur kumulatif bergeser | skor Logistic Regression karyawan jenuh (AUC 0,500) | lookback 5 bulan yang sama panjang + nilai dipotong ±5 |
| Prospek perusahaan kalah oleh karyawan di ranking gabungan | hampir tidak ada perusahaan di 10% teratas | ranking dan champion per tipe prospek |
| Memilih model dari test | risiko data snooping | champion dipilih dari validasi; test hanya untuk laporan |
| Penjelasan "nasabah mirip" NBO lemah | median 0% dari 50 tetangga graph memegang produk yang direkomendasikan | ditampilkan hanya bila lift ≥ 1,5x; selebihnya alasan dari SHAP |

## 9. Cara menjalankan

```powershell
python -m pipelines.run_offline                  # semua tahap (butuh Neo4j menyala)
python -m pipelines.run_offline --from models    # mulai dari training (Neo4j tidak perlu)
python -m pipelines.run_offline --only report    # uji signifikansi + tulis ulang docs/Hasil_Model.md
```

Hasil: model di `data/processed/models/`, skor test di `data/processed/scores/`, tabel perbandingan di `outputs/model/`, dan laporan di `docs/Hasil_Model.md`.
