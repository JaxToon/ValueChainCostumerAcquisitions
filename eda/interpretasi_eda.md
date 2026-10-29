# Interpretasi EDA Data Bank

## Ringkasan eksekutif

EDA dilakukan terhadap data yang tersedia di `synthetic_generator/output/data_bank`. Fokus bisnis utama adalah portofolio perusahaan nasabah Bank segmen Commercial dan Corporate, dengan data perorangan dianalisis sebagai konteks NBO dan ekosistem payroll/value chain.

Dataset ini sepenuhnya sintetis. Karena itu, insight di bawah ini menggambarkan aturan generator dan asumsi bisnis yang digunakan tim, bukan kondisi aktual Bank. Insight tetap berguna untuk menguji pipeline, kualitas data, desain fitur, dan demo RM Copilot.

Temuan utama:

1. Portofolio corporate/wholesale terdiri dari 1.233 perusahaan: 1.026 Commercial dan 207 Corporate.
2. Commercial lebih besar secara jumlah, sedangkan Corporate jauh lebih besar dari sisi median omzet.
3. Sektor terbesar adalah Industri Pengolahan (`C`), diikuti Pertanian (`A`) dan Konstruksi (`F`).
4. Masih terdapat ruang pembiayaan: sekitar 22,3% Commercial dan 11,6% Corporate belum memiliki fasilitas pembiayaan.
5. Produk transaksi seperti Garansi Bank memiliki jumlah riwayat tidak aktif paling besar sehingga relevan sebagai kandidat reaktivasi.
6. Data perorangan menunjukkan Tabungan Plus sebagai produk utama, sedangkan produk seperti kartu kredit, deposito, Prioritas, dan Giro memiliki penetrasi lebih rendah sehingga dapat menjadi ruang cross-sell dengan tetap memperhatikan eligibility.
7. Lonjakan saldo Corporate pada bulan ke-15 bukan insight bisnis atau musiman; sumbernya adalah outlier nominal x1000 yang sengaja ditanam pada data kotor.

---

## 1. Tujuan dan ruang lingkup EDA

EDA memiliki empat tujuan:

- memastikan kualitas data sebelum cleaning dan modeling;
- memahami komposisi nasabah perusahaan, terutama Commercial dan Corporate;
- menemukan sinyal peluang pembiayaan, cross-sell, reaktivasi, leakage, dan akuisisi value chain;
- memahami profil nasabah perorangan sebagai dasar NBO dan konteks hubungan payroll.

Analisis menggunakan data bank-visible saja. File truth di `output/kunci_evaluasi` tidak digunakan sebagai fitur maupun sumber insight operasional.

Granularitas penting dalam interpretasi:

- `companies.csv`: satu baris per perusahaan;
- `rm_portofolio.csv`: perusahaan dalam portofolio RM;
- `saldo_bulanan.csv`: satu perusahaan per bulan;
- `transaksi_counterparty_bulanan.csv`: perusahaan, counterpart, bulan, dan arah transaksi;
- `riwayat_produk_wholesale.csv`: riwayat pemakaian produk;
- `fasilitas_pembiayaan.csv`: fasilitas pembiayaan;
- `nasabah.csv`: satu nasabah perorangan;
- `nasabah_bulanan.parquet`: satu nasabah per bulan dengan status produk.

---

## 2. Kualitas data secara keseluruhan

### 2.1 Jenis masalah yang ditemukan

Data bank-visible mengandung beberapa masalah kualitas yang sengaja ditanam untuk menguji cleaning:

- missing `kisaran_pendapatan`, `pekerjaan`, `provinsi`, dan `channel` pada data nasabah;
- missing status produk dan segmen pada panel bulanan;
- missing `jumlah_transaksi`;
- missing `saldo_akhir_bulan_rp`;
- variasi kapitalisasi, spasi, dan singkatan pada provinsi, gender, pekerjaan, sektor, serta nama counterpart;
- duplikasi pada beberapa business key;
- outlier nominal positif x1000 pada transfer dan saldo.

### 2.2 Missing tidak selalu berarti error

Interpretasi missing harus dibedakan menjadi dua:

**Missing struktural** berarti atribut memang tidak tersedia bagi bank. Contoh:

- skala, omzet, jumlah karyawan, peran, payroll, dan segmen Bank pada perusahaan non-nasabah;
- demografi pada person non-nasabah;
- `bulan_keluar` yang kosong pada nasabah yang masih aktif;
- `via_anchor_id` yang kosong pada kandidat tanpa anchor.

**Missing kualitas data** adalah nilai yang seharusnya tersedia tetapi hilang karena ekstraksi atau input, misalnya `jumlah_transaksi` atau `saldo_akhir_bulan_rp`.

Konsekuensinya, missing struktural tidak boleh diimputasi secara sembarangan. Untuk modeling, missing sebaiknya diberi kategori atau flag tersendiri.

### 2.3 Dampak kualitas data terhadap insight

Insight nominal dan saldo harus dibaca setelah outlier diperiksa. Contoh pentingnya terlihat pada saldo Corporate bulan ke-15. Nilai agregat mentah melonjak karena satu nominal saldo dikali 1.000, bukan karena pertumbuhan saldo atau efek Idul Fitri. Outlier tersebut harus dikoreksi atau dikeluarkan dari agregasi sebelum menyimpulkan tren bisnis.

---

## 3. EDA nasabah perusahaan Commercial dan Corporate

### 3.1 Komposisi portofolio

Jumlah nasabah corporate/wholesale adalah 1.233 perusahaan:

| Segmen | Jumlah | Porsi debitur awal |
|---|---:|---:|
| Commercial | 1.026 | 66,7% |
| Corporate | 207 | 72,5% |

Commercial merupakan mayoritas portofolio secara jumlah. Corporate lebih kecil, tetapi memiliki skala usaha dan kebutuhan transaksi yang lebih besar. Porsi debitur Corporate juga lebih tinggi dibanding Commercial.

Implikasi bisnis:

- Commercial memberikan ruang coverage yang lebih besar karena jumlah prospeknya lebih banyak;
- Corporate lebih cocok untuk pendekatan relationship-led, pembiayaan kompleks, cash management, dan value chain;
- strategi RM sebaiknya tidak hanya memaksimalkan jumlah lead, tetapi membedakan prioritas berdasarkan segmen.

### 3.2 Sektor dominan

Sektor terbesar pada portofolio adalah:

1. `C` — Industri Pengolahan: 222 perusahaan;
2. `A` — Pertanian, Kehutanan, dan Perikanan: 191 perusahaan;
3. `F` — Konstruksi: 154 perusahaan;
4. `G` — Perdagangan: 143 perusahaan;
5. `P` — Pendidikan: 133 perusahaan.

Sektor menjadi variabel penting karena kebutuhan produk tidak sama antarindustri. Pada generator, sektor juga menjadi pemicu kebutuhan:

- `F` berkaitan dengan kebutuhan garansi bank;
- `C` dan `G` berkaitan dengan perdagangan, impor, dan SKBDN;
- `A`, `B`, dan `C` berkaitan dengan kebutuhan ekspor;
- `G` dan `I` berkaitan dengan kebutuhan QRIS/EDC untuk segmen UMKM.

Namun, distribusi sektor ini berasal dari pembobotan jumlah pekerja BPS pada generator, bukan distribusi portofolio Bank yang sebenarnya.

### 3.3 Konsentrasi wilayah

Provinsi dengan jumlah perusahaan terbanyak:

- Jawa Barat: 321 perusahaan;
- Jawa Timur: 161 perusahaan;
- Jawa Tengah: 95 perusahaan;
- Sumatera Utara: 90 perusahaan;
- Sulawesi Selatan: 77 perusahaan.

Konsentrasi tersebut dapat digunakan untuk visualisasi coverage regional dan pemilihan showcase RM. Akan tetapi, provinsi bukan bukti langsung potensi pembiayaan. Analisis lanjutan perlu menggabungkan provinsi dengan sektor, omzet, saldo, transaksi, dan status debitur.

### 3.4 Skala omzet

Median omzet tahunan yang digenerate:

- Commercial: sekitar Rp22,9 miliar;
- Corporate: sekitar Rp571,1 miliar.

Perbedaan ini mendukung pemisahan strategi:

- Commercial: peluang peningkatan pembiayaan modal kerja, cash management, dan produk transaksi pada basis nasabah yang lebih besar;
- Corporate: peluang pembiayaan bernilai besar, trade finance, supply chain financing, cash pooling, dan pengelolaan rekening perusahaan.

Angka ini merupakan output generator berdasarkan band omzet dan batas segmen, bukan estimasi aktual pasar.

---

## 4. RM portfolio dan peluang pembiayaan

Terdapat 23 RM dalam hasil generator. Sebagian besar RM memiliki sekitar 55 perusahaan pada portofolionya, sesuai asumsi `40 debitur + 15 non-debitur`.

Porsi perusahaan tanpa fasilitas:

| Segmen | Porsi tanpa fasilitas |
|---|---:|
| Commercial | 22,3% |
| Corporate | 11,6% |

Temuan ini dapat diterjemahkan menjadi dua hipotesis:

- Commercial memiliki volume peluang pembiayaan yang lebih besar;
- Corporate memiliki coverage fasilitas lebih tinggi, tetapi nilai peluang per perusahaan kemungkinan lebih besar.

Prioritas RM tidak sebaiknya hanya berdasarkan status `tanpa fasilitas`. Kandidat perlu diranking dengan kombinasi:

- saldo rata-rata dan trennya;
- arus masuk dan keluar;
- usia usaha;
- sektor dan kebutuhan produk;
- hubungan dengan anchor;
- riwayat trade atau produk transaksi;
- status debitur dan fasilitas yang telah dimiliki.

---

## 5. Produk wholesale dan reaktivasi

Dari riwayat produk wholesale, produk dengan perusahaan tidak aktif terbanyak adalah:

1. Garansi Bank: 298 perusahaan;
2. SKBDN: 100 perusahaan;
3. Impor (L/C, pembiayaan): 94 perusahaan;
4. Ekspor (L/C, negosiasi, pembiayaan): 88 perusahaan;
5. SBLC: 47 perusahaan.

Garansi Bank menjadi kandidat reaktivasi paling menonjol. Hal ini masuk akal karena produk transaksi berbasis proyek dapat berhenti setelah proyek selesai, lalu muncul kembali ketika ada proyek baru.

Insight ini tidak berarti semua perusahaan dengan produk tidak aktif harus langsung ditawarkan produk yang sama. Reaktivasi perlu mempertimbangkan:

- apakah perusahaan kembali memiliki aktivitas transaksi yang relevan;
- apakah sektor dan skala usaha masih sesuai;
- waktu sejak produk terakhir selesai;
- adanya transaksi masuk/keluar dengan counterpart baru;
- kebutuhan pembiayaan atau jaminan proyek terbaru.

---

## 6. Saldo dan transaksi counterpart

### 6.1 Saldo

Generator membuat saldo rata-rata berdasarkan omzet tahunan, hari kas, dan noise bulanan. Tidak ada pertumbuhan saldo kumulatif eksplisit dari bulan ke bulan.

Karena itu, tren saldo yang wajar adalah bergerak di sekitar baseline perusahaan dengan fluktuasi acak. Lonjakan besar harus selalu diperiksa terhadap outlier.

Pada data mentah, saldo Corporate melonjak pada bulan ke-15. Setelah ditelusuri, penyebabnya adalah satu nilai `saldo_rata2_rp` yang dikali 1.000 oleh generator data kotor. Ini bukan efek musiman Idul Fitri dan tidak boleh dibawa sebagai insight bisnis.

### 6.2 Transaksi bank lain

Porsi transaksi dengan bank lain dapat menjadi sinyal awal leakage atau peluang akuisisi, tetapi interpretasinya harus hati-hati:

- transaksi bank lain tidak otomatis berarti nasabah akan pindah bank;
- counterpart mungkin hanya menggunakan bank lain untuk kebutuhan tertentu;
- perlu melihat persistensi antarbulan, nominal, frekuensi, dan apakah counterpart tersebut berada dalam value chain anchor Bank.

Fitur yang relevan untuk model wholesale:

- nominal masuk dan keluar;
- jumlah pembayar dan penerima;
- counterpart baru dalam tiga bulan terakhir;
- porsi dana ke rekening sendiri di bank lain;
- transaksi dengan anchor Bank;
- perubahan pola transaksi antarperiode.

---

## 7. Ekosistem anchor dan value chain

Anchor merupakan titik masuk untuk memahami jaringan supplier, distributor, sub-supplier, dan pedagang perorangan. Anchor dengan banyak counterpart dan nominal transaksi besar dapat menjadi showcase yang kuat untuk demo RM Copilot.

Kriteria showcase yang disarankan:

- jumlah counterpart tinggi;
- relasi aktif pada banyak bulan;
- terdapat counterpart non-nasabah yang material;
- terdapat variasi supplier/distributor;
- sektor dan pola transaksi mudah dijelaskan;
- tidak didominasi oleh outlier nominal.

Porsi transaksi bank lain yang tinggi dapat digunakan sebagai sinyal prioritas, tetapi bukan keputusan otomatis untuk menghubungi perusahaan. Informasi tersebut perlu melewati guardrail privasi, kepatuhan, dan verifikasi RM.

---

## 8. EDA nasabah perorangan

Dataset nasabah perorangan berisi 56.487 nasabah. Usia median adalah 37 tahun.

Pekerjaan terbanyak:

1. Pegawai/Profesional: 11.798;
2. Ibu Rumah Tangga: 10.216;
3. Petani/Peternak/Pekebun/Nelayan: 8.437;
4. Pengusaha/Wiraswasta: 7.652;
5. Pekerjaan Lainnya: 6.542.

Channel akuisisi terbesar adalah Kantor Cabang dengan sekitar 73,9% nasabah, diikuti Agen Bank sekitar 16,3%, Mobile Banking sekitar 5,1%, dan Payroll Korporasi sekitar 4,7%.

Distribusi ini dapat digunakan untuk memahami asal akuisisi dan merancang segmentasi layanan. Namun, channel tidak boleh dianggap sebagai penyebab langsung kepemilikan produk karena channel juga berkorelasi dengan profil nasabah.

### 8.1 Penetrasi produk terbaru

Pada bulan ke-17, penetrasi produk tertinggi adalah:

| Produk | Penetrasi |
|---|---:|
| Tabungan Plus | 75,1% |
| Mobile Banking | 26,4% |
| Tabungan Plus Muda | 23,5% |
| Autodebit | 12,3% |
| Bank Visa Platinum | 11,0% |
| DPLK Pensiun | 6,9% |
| Bank Payroll | 5,2% |
| Bank Deposito | 3,6% |

Interpretasi bisnis:

- Tabungan Plus berfungsi sebagai produk dasar dengan penetrasi tinggi;
- mobile banking dan Tabungan Plus Muda dapat dianalisis berdasarkan usia, channel, dan aktivitas digital;
- produk dengan penetrasi rendah tidak otomatis menjadi peluang untuk semua nasabah;
- produk seperti kartu kredit, deposito, DPLK Pensiun, dan Prioritas perlu difilter berdasarkan pendapatan, usia, pekerjaan, saldo, dan eligibility.

### 8.2 Hubungan dengan nasabah corporate

Nasabah perorangan yang bekerja pada perusahaan corporate dapat dianalisis sebagai konteks payroll dan employee banking. Hubungan tersebut sebaiknya dipakai untuk memahami ekosistem dan kebutuhan layanan, bukan sebagai izin untuk menghubungi individu secara bebas.

Jenis kelamin juga lebih tepat digunakan untuk audit fairness dan pemantauan bias, bukan sebagai dasar tunggal rekomendasi produk.

---

## 9. Implikasi terhadap cleaning dan modeling

### 9.1 Aturan cleaning

Hasil EDA mendukung aturan berikut:

- standardisasi teks untuk provinsi, sektor, gender, pekerjaan, dan nama;
- deduplikasi berdasarkan business key;
- usia harus tetap valid dan tidak perlu diimputasi karena generator sekarang menjaga usia tetap lengkap;
- nominal x1000 dikoreksi jika lolos aturan outlier yang jelas dan diberi flag;
- missing struktural dipertahankan;
- missing transaksi/saldo diberi flag agar tidak tertukar dengan nilai nol;
- data kotor harus dibersihkan sebelum agregasi saldo atau transaksi.

### 9.2 Fitur model

Model perlu membedakan:

- tidak ada aktivitas transaksi;
- aktivitas ada tetapi nominal missing;
- nominal invalid dan dikeluarkan dari agregasi;
- atribut memang tidak terlihat bank.

Karena itu, selain nilai numerik, gunakan fitur indikator seperti:

- `saldo_rata2_rp_missing`;
- `saldo_rata2_rp_invalid`;
- `total_nominal_rp_missing`;
- `total_nominal_rp_x1000_corrected`;
- `jumlah_transaksi_missing`.

Jika semua `NaN` langsung diubah menjadi nol tanpa flag, model dapat salah mengartikan data invalid sebagai tidak adanya aktivitas.

---

## 10. Hipotesis lanjutan yang dapat diuji

1. Perusahaan Corporate dengan saldo besar, transaksi aktif, dan tanpa fasilitas memiliki peluang pembiayaan lebih tinggi.
2. Perusahaan sektor konstruksi dengan riwayat Garansi Bank tidak aktif merupakan kandidat reaktivasi yang menarik.
3. Counterpart baru yang berulang dan memiliki transaksi material dengan anchor Bank dapat menjadi kandidat akuisisi.
4. Porsi transaksi ke rekening sendiri di bank lain yang meningkat secara persisten dapat menjadi sinyal leakage.
5. Produk digital dan payroll memiliki pola kepemilikan berbeda menurut pekerjaan, channel, dan hubungan perusahaan.
6. Nasabah dengan produk dasar tetapi belum memiliki produk tambahan dapat menjadi kandidat NBO, selama memenuhi eligibility.
7. Perusahaan dengan banyak counterpart non-nasabah tidak otomatis merupakan prospek terbaik; kualitas hubungan, nominal, dan persistensi harus ikut dinilai.

---

## Kesimpulan

EDA menunjukkan bahwa data corporate paling informatif ketika dianalisis melalui kombinasi segmen, sektor, omzet, fasilitas, saldo, transaksi, produk, dan struktur value chain. Analisis satu kolom, seperti hanya melihat saldo atau sektor, belum cukup untuk menghasilkan prioritas RM.

Untuk data perorangan, peluang utama berada pada segmentasi produk dan konteks payroll, tetapi tetap perlu guardrail eligibility dan fairness.

Langkah berikutnya:

1. jalankan cleaning pada data baru;
2. bandingkan EDA raw dengan EDA cleaned;
3. ulangi agregasi saldo setelah outlier dikoreksi;
4. bangun fitur model dengan flag missing/invalid;
5. gunakan insight sebagai hipotesis prioritas, bukan keputusan otomatis;
6. tampilkan secara eksplisit bahwa seluruh angka berasal dari data sintetis.
