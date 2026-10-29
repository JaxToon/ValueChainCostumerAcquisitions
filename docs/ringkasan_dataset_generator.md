# Ringkasan Dataset Generator

Dokumen ini merangkum seluruh output generator pada folder `data_bank` dan `kunci_evaluasi`.

## Perbedaan folder

`data_bank` berisi data yang diasumsikan dapat dilihat bank. Folder ini digunakan untuk EDA, cleaning, feature engineering, graph, modeling, dan aplikasi. Folder ini sengaja diberi data kotor terkontrol.

`kunci_evaluasi` berisi truth lengkap dan log generator. Folder ini hanya untuk evaluasi dan tidak boleh digunakan sebagai fitur karena menyebabkan data leakage.

## 1. Dataset data_bank

| File | Baris | Granularitas | Fungsi |
|---|---:|---|---|
| `nasabah.csv` | 56.487 | satu nasabah Bank | Profil KYC nasabah perorangan |
| `nasabah_bulanan.parquet` | 888.412 | satu nasabah per bulan | Panel produk dan status nasabah |
| `companies.csv` | 19.994 | satu perusahaan terlihat bank | Profil perusahaan dan sektor |
| `persons.csv` | 74.406 | satu orang terlihat bank | Nasabah, karyawan, dan counterpart |
| `employment.csv` | 30.637 | satu relasi orang-perusahaan | Karyawan, pemilik, dan pembeli |
| `transfers_monthly.csv` | 801.599 | satu pasangan per bulan | Transfer dengan minimal satu sisi Bank |
| `acquisitions.csv` | 32.720 | satu kandidat non-nasabah | Target akuisisi |
| `rm_portofolio.csv` | 1.233 | satu perusahaan per RM | Portofolio RM wholesale |
| `transaksi_counterparty_bulanan.csv` | 571.316 | perusahaan-counterpart-bulan-arah | Aktivitas counterpart |
| `saldo_bulanan.csv` | 86.683 | satu perusahaan per bulan | Saldo rata-rata dan akhir |
| `riwayat_produk_wholesale.csv` | 15.223 | satu pemakaian produk | Riwayat wholesale/trade |
| `fasilitas_pembiayaan.csv` | 2.942 | satu fasilitas | Fasilitas pembiayaan |
| `lead_bisdev.csv` | 1.545 | satu lead | Lead Bisdev dan entity resolution |
| `label_wholesale.csv` | 2.081 | satu kejadian label | Target wholesale |
| `produk_level.csv` | 12 | satu produk | Benchmark NBO |
| `kamus_data.csv` | 44 | satu definisi kolom | Visibility dan eligibility fitur |

### `nasabah.csv`

Profil nasabah perorangan: ID, usia, gender, provinsi, perkotaan, pekerjaan, waktu masuk/keluar, lama menjadi nasabah, channel, dan kisaran pendapatan. Digunakan untuk EDA demografi, segmentasi, channel akuisisi, NBO, dan audit fairness.

### `nasabah_bulanan.parquet`

Panel 17 bulan per nasabah. Kolom `prod_*` berisi status kepemilikan produk, sedangkan `segmen`, `aktif`, dan lama nasabah memberi konteks waktu. Digunakan untuk NBO dan analisis perubahan produk.

### `companies.csv`

Profil perusahaan Bank atau perusahaan yang terlihat melalui transaksi. Berisi sektor, provinsi, skala, omzet, jumlah karyawan, tahun berdiri, anchor, status Bank, produk, segmen, status debitur, RM, dan cabang. Atribut internal Bank non-nasabah sengaja kosong.

### `persons.csv`

Person yang terlihat melalui rekening, payroll, transfer, atau relasi perusahaan. Data KYC lengkap untuk nasabah Bank; person non-nasabah hanya memiliki informasi yang terlihat bank.

### `employment.csv`

Relasi orang-perusahaan dengan peran `KARYAWAN`, `PEMILIK`, atau `PEMBELI`. Digunakan untuk graph `WORKS_AT`, `OWNS`, dan `BUYS_FROM`, serta analisis payroll/value chain.

### `transfers_monthly.csv`

Transfer bulanan dengan `from_id`, `to_id`, nominal, jumlah transaksi, dan jenis relasi terlihat. Digunakan untuk graph, fitur nominal/frekuensi, akuisisi, dan value chain. Transfer antar dua pihak non-nasabah tidak diekspor.

### `acquisitions.csv`

Kandidat non-nasabah terlihat bank, waktu menjadi nasabah, produk pertama, jendela validasi/test, dan anchor penghubung. File ini adalah target akuisisi, bukan fitur.

### `rm_portofolio.csv`

Daftar perusahaan dalam portofolio RM beserta segmen dan status debitur awal. Digunakan untuk coverage RM dan peluang non-debitur.

### `transaksi_counterparty_bulanan.csv`

Detail transaksi perusahaan dengan counterpart, termasuk arah, nominal, frekuensi, nama, bank, kelas nama-bank, dan channel. Digunakan untuk sinyal counterpart baru, leakage, transaksi bank lain, dan hubungan anchor.

### `saldo_bulanan.csv`

Saldo rata-rata dan saldo akhir perusahaan per bulan. Digunakan untuk likuiditas, tren saldo, dan fitur kebutuhan pembiayaan. Outlier harus dibersihkan sebelum agregasi.

### `riwayat_produk_wholesale.csv`

Riwayat produk wholesale/trade finance, tanggal mulai/selesai, status, beneficiary, dan nilai proyek. Digunakan untuk cross-sell dan reaktivasi.

### `fasilitas_pembiayaan.csv`

Produk fasilitas, plafon, baki debet, tanggal mulai, dan jatuh tempo. Digunakan untuk coverage pembiayaan dan target debitur baru.

### `lead_bisdev.csv`

Lead Bisdev yang sering belum memiliki `company_id`. Digunakan untuk menguji entity resolution berdasarkan nama perusahaan dan anchor.

### `label_wholesale.csv`

Target `cross_sell_wholesale`, `non_debitur_ke_debitur`, `reaktivasi`, dan `leakage`. Tidak boleh digunakan sebagai fitur.

### `produk_level.csv`

Target level kepemilikan produk dan sumber pembentukannya untuk benchmark mesin NBO.

### `kamus_data.csv`

Data dictionary yang menjelaskan status HIJAU/KUNING/ORANYE/MERAH, visibility, sumber dunia nyata, kelayakan fitur, dan catatan batasan.

## 2. Dataset kunci_evaluasi

| File | Baris | Isi | Penggunaan |
|---|---:|---|---|
| `nasabah_lengkap.csv` | 55.928 | Profil nasabah dengan pendapatan numerik pasti | Evaluasi cleaning |
| `persons_lengkap.csv` | 85.932 | Data lengkap seluruh person | Evaluasi visibility |
| `companies_lengkap.csv` | 20.050 | Data lengkap seluruh perusahaan | Evaluasi export/cleaning |
| `employment_lengkap.csv` | 43.127 | Seluruh relasi orang-perusahaan | Evaluasi visibility |
| `transfers_lengkap.csv` | 856.640 | Semua transfer, termasuk non-nasabah | Evaluasi filtering |
| `acquisitions_lengkap.csv` | 44.955 | Label akuisisi lengkap | Evaluasi target |
| `relationship_truth.csv` | 77.324 | Relasi value chain sebenarnya | Evaluasi graph |
| `lead_bisdev_kunci.csv` | 1.500 | Mapping lead ke company/anchor | Evaluasi entity resolution |
| `counterparty_pindah_bank.csv` | 449 | Truth counterpart pindah bank | Evaluasi leakage |
| `catatan_data_kotor.csv` | 121.396 | Log perubahan dirty generator | Audit cleaning |

### Penjelasan file truth

- `nasabah_lengkap.csv`: versi lengkap nasabah dengan `pendapatan_bulanan_idr`; data angka pasti ini tidak tersedia di bank view.
- `persons_lengkap.csv`: seluruh person dengan atribut demografi, termasuk atribut non-nasabah yang disembunyikan pada export.
- `companies_lengkap.csv`: seluruh perusahaan dengan omzet, skala, jumlah karyawan, peran, payroll, dan segmen lengkap.
- `employment_lengkap.csv`: seluruh relasi orang-perusahaan, termasuk relasi yang tidak terlihat bank.
- `transfers_lengkap.csv`: semua transfer, termasuk transfer antar dua pihak non-nasabah.
- `acquisitions_lengkap.csv`: seluruh kandidat dan label akuisisi, bukan hanya kandidat yang terlihat bank.
- `relationship_truth.csv`: hubungan payer-payee/value chain sebenarnya untuk evaluasi graph.
- `lead_bisdev_kunci.csv`: mapping truth lead ke `company_id` dan anchor untuk entity resolution.
- `counterparty_pindah_bank.csv`: truth perpindahan bank counterpart untuk evaluasi sinyal leakage.
- `catatan_data_kotor.csv`: log `file`, `kolom`, `jenis`, `id`, `nilai_asli`, dan `nilai_kotor` dari `dirty.py`.

## 3. Relasi utama

Dataset utama saling terhubung melalui:

- `person_id`: nasabah, person, dan employment;
- `company_id`: perusahaan, RM, saldo, transaksi, produk, fasilitas, dan label;
- `bulan_ke`: seluruh panel bulanan;
- `lead_id`: lead Bisdev;
- `entity_id`: kandidat akuisisi.

Relasi konseptualnya adalah nasabah terhubung ke panel produk, employment, dan akuisisi; perusahaan terhubung ke RM, saldo, transaksi, produk, fasilitas, label, dan employment; person terhubung ke employment dan transfer.

## 4. Aturan penggunaan

Gunakan `data_bank` setelah cleaning dan gunakan `kamus_data.csv` untuk menentukan kolom yang boleh menjadi fitur.

Jangan gunakan sebagai fitur:

- seluruh isi `kunci_evaluasi`;
- `catatan_data_kotor.csv`;
- `relationship_truth.csv`;
- `lead_bisdev_kunci.csv`;
- label akuisisi dan `label_wholesale`;
- pendapatan numerik pasti dari `nasabah_lengkap.csv`;
- atribut non-nasabah yang hanya tersedia dalam truth lengkap.

Jumlah baris `data_bank` dapat berbeda dari truth karena dirty generator menambahkan duplikasi. Perbandingan harus dilakukan setelah deduplikasi berdasarkan business key.

## Kesimpulan

`data_bank` merepresentasikan data operasional yang terbatas pada apa yang terlihat oleh bank. `kunci_evaluasi` merepresentasikan dunia lengkap yang diketahui generator. Pemisahan keduanya mencegah data leakage dan membuat evaluasi cleaning, export, entity resolution, graph, serta model dapat dilakukan secara terukur.
