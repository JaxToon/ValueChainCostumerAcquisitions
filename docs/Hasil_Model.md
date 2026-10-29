# Hasil Model — RM Copilot Value Chain

Dibuat otomatis dari run terakhir pipeline (`python -m pipelines.run_offline`), 29 Oktober 2026. Semua data sintetis; angka adalah hasil simulasi, bukan performa di data Bank.

## Cara membaca

- **Walk-forward**: model dilatih di jendela lama dan diuji di jendela yang lebih baru, sehingga tidak ada data masa depan yang bocor.
- **PR-AUC validasi**: dihitung di 25% data jendela train yang disisihkan. Champion dipilih dari angka ini, **tidak** dari test.
- **Test**: jendela terbaru yang tidak pernah dipakai melatih atau memilih model.
- **Baseline bisnis**: cara kerja RM tanpa sistem (prospek dengan nominal terbesar, produk terpopuler, dan sejenisnya).
- **Lift desil 1**: berapa kali lebih banyak konversi di 10% teratas dibanding memilih acak.

## Ringkasan

| Mesin | Champion | ROC-AUC test | Baseline | PR-AUC test | Baseline | Porsi pengaruh graph (SHAP) |
| --- | --- | --- | --- | --- | --- | --- |
| Akuisisi (semua prospek) | LightGBM + graph | 0,725 | 0,529 | 0,187 | 0,072 | 60,7% |
| Akuisisi: prospek perusahaan (daftar RM Commercial) | Logistic Regression | 0,694 | 0,683 | 0,099 | 0,097 | 58,7% |
| Akuisisi: pedagang (lewat program anchor) | Logistic Regression | 0,747 | 0,488 | 0,265 | 0,053 | 56,7% |
| Akuisisi: karyawan (lewat Payroll Korporasi) | LightGBM + graph (oversampling) | 0,707 | 0,524 | 0,215 | 0,087 | 75,7% |
| Wholesale: cross-sell produk baru | Logistic Regression | 0,811 | 0,747 | 0,440 | 0,301 | 28,8% |
| Wholesale: non-debitur ke debitur | Baseline bisnis | 0,692 | 0,692 | 0,151 | 0,151 | 0,0% |
| Wholesale: reaktivasi produk trade | Logistic Regression | 0,646 | 0,457 | 0,221 | 0,131 | 64,3% |
| Wholesale: leakage (dana pindah ke rekening sendiri di bank lain) | Logistic Regression | 0,707 | 0,661 | 0,150 | 0,073 | 24,4% |
| NBO: cross-sell produk ritel | LightGBM + graph | 0,946 | 0,808 | 0,102 | 0,007 | 17,1% |

## Akuisisi (semua prospek)

- Train: fitur bulan 1-5, label bulan 6-11; 32.720 baris, 1.796 positif.
- Test: fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17; 30.924 baris, 1.723 positif (base rate 5,6%).
- Champion: **LightGBM + graph**, PR-AUC validasi tertinggi (0,340). Di test: ROC-AUC 0,725 vs baseline 0,529, PR-AUC 0,187 vs 0,072.

| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | Precision@10% | Lift desil 1 | F1 | Champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline bisnis | 0,060 | 0,529 | 0,072 | 8,8% | 1,58x | 0,113 |  |
| Logistic Regression | 0,337 | 0,733 | 0,191 | 19,3% | 3,47x | 0,248 |  |
| Random Forest | 0,309 | 0,724 | 0,191 | 19,1% | 3,42x | 0,245 |  |
| XGBoost | 0,318 | 0,696 | 0,171 | 17,9% | 3,20x | 0,229 |  |
| LightGBM tanpa graph | 0,090 | 0,617 | 0,078 | 8,2% | 1,47x | 0,106 |  |
| LightGBM + graph | 0,340 | 0,725 | 0,187 | 19,1% | 3,42x | 0,245 | **ya** |
| LightGBM + graph (oversampling) | 0,328 | 0,720 | 0,184 | 19,2% | 3,45x | 0,247 |  |

## Akuisisi: prospek perusahaan (daftar RM Commercial)

- Train: fitur bulan 1-5, label bulan 6-11; 14.242 baris, 456 positif.
- Test: fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17; 13.786 baris, 559 positif (base rate 4,1%).
- Champion: **Logistic Regression**, PR-AUC validasi tertinggi (0,079). Di test: ROC-AUC 0,694 vs baseline 0,683, PR-AUC 0,099 vs 0,097.

| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | Precision@10% | Lift desil 1 | F1 | Champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline bisnis | 0,076 | 0,683 | 0,097 | 11,9% | 2,94x | 0,169 |  |
| Logistic Regression | 0,079 | 0,694 | 0,099 | 12,0% | 2,97x | 0,171 | **ya** |
| Random Forest | 0,067 | 0,680 | 0,100 | 10,7% | 2,61x | 0,152 |  |
| XGBoost | 0,060 | 0,625 | 0,067 | 8,1% | 2,00x | 0,116 |  |
| LightGBM tanpa graph | 0,053 | 0,630 | 0,073 | 8,2% | 2,02x | 0,117 |  |
| LightGBM + graph | 0,078 | 0,689 | 0,100 | 11,7% | 2,90x | 0,167 |  |
| LightGBM + graph (oversampling) | 0,070 | 0,687 | 0,102 | 11,2% | 2,76x | 0,159 |  |

## Akuisisi: pedagang (lewat program anchor)

- Train: fitur bulan 1-5, label bulan 6-11; 6.478 baris, 297 positif.
- Test: fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17; 6.181 baris, 305 positif (base rate 4,9%).
- Champion: **Logistic Regression**, PR-AUC validasi tertinggi (0,413). Di test: ROC-AUC 0,747 vs baseline 0,488, PR-AUC 0,265 vs 0,053.

| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | Precision@10% | Lift desil 1 | F1 | Champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline bisnis | 0,061 | 0,488 | 0,053 | 4,9% | 0,98x | 0,065 |  |
| Logistic Regression | 0,413 | 0,747 | 0,265 | 22,7% | 4,59x | 0,303 | **ya** |
| Random Forest | 0,268 | 0,744 | 0,248 | 22,2% | 4,49x | 0,297 |  |
| XGBoost | 0,317 | 0,693 | 0,219 | 18,1% | 3,67x | 0,243 |  |
| LightGBM tanpa graph | 0,042 | 0,533 | 0,057 | 5,3% | 1,08x | 0,072 |  |
| LightGBM + graph | 0,368 | 0,730 | 0,243 | 20,4% | 4,13x | 0,273 |  |
| LightGBM + graph (oversampling) | 0,345 | 0,723 | 0,242 | 20,2% | 4,10x | 0,271 |  |

## Akuisisi: karyawan (lewat Payroll Korporasi)

- Train: fitur bulan 1-5, label bulan 6-11; 12.000 baris, 1.043 positif.
- Test: fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17; 10.957 baris, 859 positif (base rate 7,8%).
- Champion: **LightGBM + graph (oversampling)**, PR-AUC validasi tertinggi (0,389). Di test: ROC-AUC 0,707 vs baseline 0,524, PR-AUC 0,215 vs 0,087.

| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | Precision@10% | Lift desil 1 | F1 | Champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline bisnis | 0,085 | 0,524 | 0,087 | 9,1% | 1,16x | 0,102 |  |
| Logistic Regression | 0,379 | 0,722 | 0,221 | 24,0% | 3,06x | 0,269 |  |
| Random Forest | 0,362 | 0,714 | 0,222 | 24,5% | 3,12x | 0,275 |  |
| XGBoost | 0,344 | 0,694 | 0,203 | 24,3% | 3,10x | 0,272 |  |
| LightGBM tanpa graph | 0,092 | 0,505 | 0,080 | 8,0% | 1,03x | 0,090 |  |
| LightGBM + graph | 0,371 | 0,706 | 0,210 | 24,6% | 3,15x | 0,276 |  |
| LightGBM + graph (oversampling) | 0,389 | 0,707 | 0,215 | 23,8% | 3,04x | 0,267 | **ya** |

## Wholesale: cross-sell produk baru

- Train: fitur bulan 1-5, label bulan 6-11; 5.099 baris, 569 positif.
- Test: fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17; 5.099 baris, 543 positif (base rate 10,6%).
- Champion: **Logistic Regression**, PR-AUC validasi tertinggi (0,424). Di test: ROC-AUC 0,811 vs baseline 0,747, PR-AUC 0,440 vs 0,301.

| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | Precision@10% | Lift desil 1 | F1 | Champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline bisnis | 0,242 | 0,747 | 0,301 | 36,9% | 3,45x | 0,357 |  |
| Logistic Regression | 0,424 | 0,811 | 0,440 | 43,5% | 4,10x | 0,422 | **ya** |
| Random Forest | 0,396 | 0,801 | 0,421 | 41,2% | 3,87x | 0,399 |  |
| XGBoost | 0,332 | 0,771 | 0,383 | 39,6% | 3,73x | 0,384 |  |
| LightGBM tanpa graph | 0,325 | 0,776 | 0,393 | 39,0% | 3,65x | 0,378 |  |
| LightGBM + graph | 0,383 | 0,797 | 0,415 | 40,8% | 3,84x | 0,395 |  |
| LightGBM + graph (oversampling) | 0,379 | 0,796 | 0,416 | 41,6% | 3,91x | 0,403 |  |

## Wholesale: non-debitur ke debitur

- Train: fitur bulan 1-5, label bulan 6-11; 3.328 baris, 255 positif.
- Test: fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17; 3.073 baris, 235 positif (base rate 7,6%).
- Champion: **Baseline bisnis**, PR-AUC validasi tertinggi (0,290). Aturan bisnis menang di validasi, jadi sistem memakai aturan, bukan ML.

| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | Precision@10% | Lift desil 1 | F1 | Champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline bisnis | 0,290 | 0,692 | 0,151 | 15,6% | 2,04x | 0,177 | **ya** |
| Logistic Regression | 0,204 | 0,711 | 0,168 | 19,5% | 2,56x | 0,221 |  |
| Random Forest | 0,259 | 0,723 | 0,193 | 23,1% | 3,02x | 0,262 |  |
| XGBoost | 0,251 | 0,676 | 0,155 | 19,2% | 2,51x | 0,218 |  |
| LightGBM tanpa graph | 0,241 | 0,625 | 0,126 | 15,0% | 1,96x | 0,170 |  |
| LightGBM + graph | 0,264 | 0,694 | 0,180 | 21,5% | 2,81x | 0,244 |  |
| LightGBM + graph (oversampling) | 0,285 | 0,699 | 0,181 | 19,9% | 2,60x | 0,225 |  |

## Wholesale: reaktivasi produk trade

- Train: fitur bulan 1-5, label bulan 6-11; 849 baris, 131 positif.
- Test: fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17; 781 baris, 111 positif (base rate 14,2%).
- Champion: **Logistic Regression**, PR-AUC validasi tertinggi (0,276). Di test: ROC-AUC 0,646 vs baseline 0,457, PR-AUC 0,221 vs 0,131.

| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | Precision@10% | Lift desil 1 | F1 | Champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline bisnis | 0,190 | 0,457 | 0,131 | 11,5% | 0,81x | 0,095 |  |
| Logistic Regression | 0,276 | 0,646 | 0,221 | 20,5% | 1,44x | 0,169 | **ya** |
| Random Forest | 0,223 | 0,669 | 0,221 | 23,1% | 1,62x | 0,190 |  |
| XGBoost | 0,245 | 0,582 | 0,213 | 23,1% | 1,62x | 0,190 |  |
| LightGBM tanpa graph | 0,198 | 0,551 | 0,173 | 19,2% | 1,35x | 0,159 |  |
| LightGBM + graph | 0,228 | 0,583 | 0,217 | 20,5% | 1,44x | 0,169 |  |
| LightGBM + graph (oversampling) | 0,241 | 0,596 | 0,210 | 19,2% | 1,35x | 0,159 |  |

## Wholesale: leakage (dana pindah ke rekening sendiri di bank lain)

- Train: fitur bulan 1-5, label bulan 6-11; 2.569 baris, 121 positif.
- Test: fitur aktivitas bulan 7-11 dan graph sampai bulan 11, label bulan 12-17; 2.448 baris, 116 positif (base rate 4,7%).
- Champion: **Logistic Regression**, PR-AUC validasi tertinggi (0,120). Di test: ROC-AUC 0,707 vs baseline 0,661, PR-AUC 0,150 vs 0,073.

| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | Precision@10% | Lift desil 1 | F1 | Champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline bisnis | 0,071 | 0,661 | 0,073 | 7,8% | 1,64x | 0,105 |  |
| Logistic Regression | 0,120 | 0,707 | 0,150 | 12,2% | 2,59x | 0,166 | **ya** |
| Random Forest | 0,094 | 0,707 | 0,135 | 15,1% | 3,11x | 0,205 |  |
| XGBoost | 0,093 | 0,633 | 0,082 | 10,2% | 2,16x | 0,139 |  |
| LightGBM tanpa graph | 0,063 | 0,596 | 0,074 | 8,6% | 1,82x | 0,116 |  |
| LightGBM + graph | 0,101 | 0,694 | 0,111 | 12,7% | 2,68x | 0,172 |  |
| LightGBM + graph (oversampling) | 0,100 | 0,681 | 0,102 | 10,6% | 2,25x | 0,144 |  |

## NBO: cross-sell produk ritel

- Train: fitur bulan 13-15, label bulan 14-16 (negative sampling 15%); 268.622 baris, 4.040 positif.
- Test: fitur bulan 16, label bulan 17; 596.049 baris, 1.328 positif (base rate 0,2%).
- Champion: **LightGBM + graph**, PR-AUC validasi tertinggi (0,342). Di test: ROC-AUC 0,946 vs baseline 0,808, PR-AUC 0,102 vs 0,007.

| Model | PR-AUC validasi | ROC-AUC test | PR-AUC test | Precision@10% | Lift desil 1 | F1 | Champion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline bisnis | 0,039 | 0,808 | 0,007 | - | 2,93x | 0,006 |  |
| Logistic Regression | 0,093 | 0,907 | 0,016 | - | 6,90x | 0,029 |  |
| Random Forest | 0,266 | 0,941 | 0,074 | - | 8,32x | 0,092 |  |
| XGBoost | 0,294 | 0,935 | 0,076 | - | 7,98x | 0,079 |  |
| LightGBM tanpa graph | 0,297 | 0,942 | 0,098 | - | 8,16x | 0,101 |  |
| LightGBM + graph | 0,342 | 0,946 | 0,102 | - | 8,40x | 0,120 | **ya** |
| LightGBM + graph (oversampling) | 0,323 | 0,946 | 0,078 | - | 8,46x | 0,121 |  |

Metrik per nasabah (nasabah yang benar-benar membeli di bulan test):

| Model | Hit@1 | Recall@1 | Hit@3 | Recall@3 |
| --- | --- | --- | --- | --- |
| LightGBM + graph | 71,0% | 70,2% | 31,3% | 92,9% |
| Baseline bisnis | 26,7% | 26,4% | 26,5% | 78,7% |

## Uji signifikansi (paired bootstrap, 95%)

Baris test di-resample 1.000 kali (NBO: 200 kali, per nasabah), kedua model dinilai pada sampel yang sama. Interval yang tidak memuat 0 berarti selisihnya bukan kebetulan.

**Champion vs baseline bisnis**

| Mesin | Selisih ROC-AUC [CI 95%] | Signifikan | Selisih PR-AUC [CI 95%] | Signifikan |
| --- | --- | --- | --- | --- |
| Akuisisi (semua prospek) | 0,193 [0,172; 0,212] | ya | 0,112 [0,095; 0,130] | ya |
| Akuisisi: prospek perusahaan (daftar RM Commercial) | 0,011 [-0,001; 0,023] | **tidak** | 0,003 [-0,005; 0,010] | **tidak** |
| Akuisisi: pedagang (lewat program anchor) | 0,260 [0,217; 0,302] | ya | 0,209 [0,161; 0,265] | ya |
| Akuisisi: karyawan (lewat Payroll Korporasi) | 0,187 [0,159; 0,213] | ya | 0,129 [0,106; 0,155] | ya |
| Wholesale: cross-sell produk baru | 0,065 [0,050; 0,082] | ya | 0,132 [0,104; 0,159] | ya |
| Wholesale: non-debitur ke debitur | 0,000 [0,000; 0,000] | **tidak** | 0,000 [0,000; 0,000] | **tidak** |
| Wholesale: reaktivasi produk trade | 0,181 [0,107; 0,257] | ya | 0,080 [0,035; 0,133] | ya |
| Wholesale: leakage (dana pindah ke rekening sendiri di bank lain) | 0,048 [-0,003; 0,095] | **tidak** | 0,080 [0,036; 0,138] | ya |
| NBO: cross-sell produk ritel | 0,136 [0,129; 0,143] | ya | 0,078 [0,068; 0,090] | ya |

**Ablation graph: LightGBM + graph vs LightGBM tanpa graph**

| Mesin | Selisih ROC-AUC [CI 95%] | Signifikan | Selisih PR-AUC [CI 95%] | Signifikan |
| --- | --- | --- | --- | --- |
| Akuisisi (semua prospek) | 0,108 [0,095; 0,121] | ya | 0,109 [0,094; 0,127] | ya |
| Akuisisi: prospek perusahaan (daftar RM Commercial) | 0,059 [0,040; 0,079] | ya | 0,027 [0,013; 0,042] | ya |
| Akuisisi: pedagang (lewat program anchor) | 0,196 [0,155; 0,237] | ya | 0,186 [0,142; 0,237] | ya |
| Akuisisi: karyawan (lewat Payroll Korporasi) | 0,201 [0,175; 0,228] | ya | 0,130 [0,109; 0,157] | ya |
| Wholesale: cross-sell produk baru | 0,021 [0,009; 0,034] | ya | 0,021 [-0,001; 0,043] | **tidak** |
| Wholesale: non-debitur ke debitur | 0,068 [0,030; 0,105] | ya | 0,054 [0,022; 0,091] | ya |
| Wholesale: reaktivasi produk trade | 0,033 [-0,021; 0,086] | **tidak** | 0,044 [-0,008; 0,094] | **tidak** |
| Wholesale: leakage (dana pindah ke rekening sendiri di bank lain) | 0,097 [0,033; 0,156] | ya | 0,038 [0,006; 0,077] | ya |
| NBO: cross-sell produk ritel | 0,005 [0,004; 0,006] | ya | 0,004 [-0,001; 0,011] | **tidak** |

## Data tidak seimbang: class weights vs oversampling

Grill me Q23 dan PRD: class_weight atau random oversampling, hanya di data train, tanpa SMOTE. Keduanya diuji dengan parameter LightGBM yang sama; yang dipakai adalah yang menang di validasi.

| Mesin | PR-AUC validasi (class weights) | PR-AUC validasi (oversampling) | PR-AUC test (class weights) | PR-AUC test (oversampling) |
| --- | --- | --- | --- | --- |
| Akuisisi (semua prospek) | 0,340 | 0,328 | 0,187 | 0,184 |
| Akuisisi: prospek perusahaan (daftar RM Commercial) | 0,078 | 0,070 | 0,100 | 0,102 |
| Akuisisi: pedagang (lewat program anchor) | 0,368 | 0,345 | 0,243 | 0,242 |
| Akuisisi: karyawan (lewat Payroll Korporasi) | 0,371 | 0,389 | 0,210 | 0,215 |
| Wholesale: cross-sell produk baru | 0,383 | 0,379 | 0,415 | 0,416 |
| Wholesale: non-debitur ke debitur | 0,264 | 0,285 | 0,180 | 0,181 |
| Wholesale: reaktivasi produk trade | 0,228 | 0,241 | 0,217 | 0,210 |
| Wholesale: leakage (dana pindah ke rekening sendiri di bank lain) | 0,101 | 0,100 | 0,111 | 0,102 |
| NBO: cross-sell produk ritel | 0,342 | 0,323 | 0,102 | 0,078 |

## Kalibrasi peluang

Ranking nilai harapan (peluang x nilai - biaya) hanya benar bila peluangnya terkalibrasi. ECE = rata-rata selisih antara peluang prediksi dan konversi aktual per desil (0 = sempurna). Grafik di halaman Model dan Monitoring.

| Mesin | ECE |
| --- | --- |
| Akuisisi (semua prospek) | 0,010 |
| Akuisisi: prospek perusahaan (daftar RM Commercial) | 0,006 |
| Akuisisi: pedagang (lewat program anchor) | 0,007 |
| Akuisisi: karyawan (lewat Payroll Korporasi) | 0,020 |
| Wholesale: cross-sell produk baru | 0,017 |
| Wholesale: reaktivasi produk trade | 0,041 |
| Wholesale: leakage (dana pindah ke rekening sendiri di bank lain) | 0,010 |
| NBO: cross-sell produk ritel | 0,014 |

## Fairness

Disparate impact = tingkat rekomendasi kelompok terendah dibagi tertinggi (tanda bila di bawah 0,8). Equal opportunity = recall kelompok terendah dibagi tertinggi (apakah pembeli sungguhan di setiap kelompok sama-sama ditemukan). Rasio base rate menunjukkan seberapa besar perbedaan itu memang ada di data.

| Mesin | Atribut | Disparate impact | Equal opportunity | Rasio base rate |
| --- | --- | --- | --- | --- |
| nbo | jenis_kelamin | 0,55 | 0,74 | 0,74 |
| nbo | kelompok_usia | 0,00 | 0,00 | 0,08 |
| nbo | provinsi | 0,35 | 0,00 | 0,00 |
| akuisisi | kelompok_volume | 0,30 | 0,38 | 0,77 |
| akuisisi | tipe_prospek | 0,09 | 0,17 | 0,52 |
| akuisisi (peringkat per tipe) | kelompok_volume | 0,36 | 0,79 | 0,77 |
| akuisisi (peringkat per tipe) | tipe_prospek | 0,99 | 0,59 | 0,52 |

Jenis kelamin tidak pernah dipakai sebagai fitur; selisih berasal dari fitur yang berkorelasi (penghasilan, pekerjaan). Nasabah 25 tahun ke bawah jarang direkomendasikan karena syarat produk (kartu kredit 21+ dan penghasilan minimal Rp3 juta). Untuk akuisisi, aplikasi meranking prospek di dalam tipenya, sehingga perusahaan tidak kalah oleh karyawan yang base rate-nya lebih tinggi.

## Pembersihan data (EDA)

| File | Kolom | Baris | Sama dengan data asli | Masih kosong |
| --- | --- | --- | --- | --- |
| nasabah | provinsi | 55.928 | 100,0% | 2,0% |
| nasabah | jenis_kelamin | 55.928 | 100,0% | 0,0% |
| nasabah | pekerjaan | 55.928 | 100,0% | 3,0% |
| nasabah | usia_bulan1 | 55.928 | 100,0% | 0,3% |
| nasabah | (duplikat) | 55.928 | 100,0% | 0,0% |
| companies | provinsi | 19.994 | 100,0% | 0,0% |
| companies | sektor | 19.994 | 100,0% | 0,0% |
| transfers | total_nominal_rp | 797.611 | 100,0% | 0,0% |
| lead_bisdev | company_id (entity resolution) | 1.500 | 100,0% | 0,0% |

## Catatan metodologi (pitfall yang ditemukan dan diperbaiki)

| Masalah | Gejala | Perbaikan |
| --- | --- | --- |
| Koordinat embedding FastRP tidak sejajar antar jendela | Model yang memakai embedding mentah turun saat diuji di jendela berikutnya | Embedding mentah diganti kemiripan di dalam satu jendela (mirip nasabah Bank, mirip debitur); NBO memakai kemiripan nasabah-produk |
| Fitur kumulatif bergeser antar jendela | Bulan aktif 5 vs 11, nominal total membesar; skor Logistic Regression jenuh (AUC 0,500) | Semua fitur aktivitas memakai 5 bulan terakhir yang sama panjang |
| Fitur hampir konstan di train | Bulan THR hanya ada di jendela train untuk karyawan | Nilai standar di Logistic Regression dipotong ke rentang -5 sampai 5 |
| Prospek perusahaan kalah oleh karyawan di peringkat gabungan | Hampir tidak ada perusahaan di 10% teratas | Peringkat dan champion per tipe prospek |
| Batas sinyal prospek perusahaan | Yang terlihat bank hanya transaksi dengan nasabah Bank; volume itu sudah ditangkap baseline nominal | Dilaporkan jujur; nilai tambah sistem untuk perusahaan ada di sinyal F19, jangkauan dua langkah, dan konteks |
| Pemilihan model dari test | Risiko data snooping | Champion dipilih dari PR-AUC validasi; test hanya untuk laporan |
| Penjelasan 'nasabah mirip' NBO lemah | Median 0% dari 50 tetangga graph memegang produk yang direkomendasikan (lift rata-rata 0,34x) | Kalimat tetangga hanya ditampilkan bila lift >= 1,5x (sekitar 9% rekomendasi); selebihnya alasan dari SHAP |
