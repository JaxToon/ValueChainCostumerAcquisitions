# Ringkasan Data Cleaning

Dokumen ini menjelaskan proses cleaning pada `src/data/clean.py`, alasan setiap perlakuan, serta perbedaannya dengan versi awal pipeline cleaning.

Sumber data yang dibersihkan adalah:

```text
synthetic_generator/output/data_bank/
```

Data truth di `synthetic_generator/output/kunci_evaluasi/` hanya digunakan untuk evaluasi, bukan sebagai sumber imputasi atau fitur model.

---

## 1. Prinsip utama cleaning

Cleaning tidak bertujuan membuat semua sel pasti terisi. Tujuannya adalah memastikan bahwa:

- nilai memiliki format dan kategori yang konsisten;
- duplikasi berdasarkan business key dihapus;
- nilai invalid tidak masuk ke agregasi atau model tanpa penanganan;
- missing struktural tidak dianggap sebagai error;
- nilai hasil imputasi dapat ditelusuri melalui flag;
- tidak ada fakta nasabah yang diciptakan tanpa dasar.

Perbedaan penting:

> Data bersih tidak selalu berarti data tanpa `NaN`. Data bersih berarti setiap `NaN` dan nilai hasil imputasi memiliki interpretasi yang jelas.

---

## 2. Validasi kualitas data

Sebelum output ditulis, `clean.py` menjalankan `validate_cleaned()`.

Validasi meliputi:

### 2.1 Validasi skema

Memastikan dataset dan kolom wajib tersedia, misalnya:

- `person_id` pada nasabah;
- `company_id` pada perusahaan;
- `bulan_ke` pada data bulanan;
- `total_nominal_rp` pada transfer;
- `saldo_rata2_rp` dan `saldo_akhir_bulan_rp` pada saldo.

### 2.2 Validasi critical null

Identifier dan usia nasabah wajib terisi:

- `person_id`;
- `company_id`;
- `lead_id`;
- `bulan_ke`;
- `usia_bulan1`;
- `usia` pada panel bulanan.

Jika usia hilang, pipeline gagal. Usia tidak diimputasi karena umur merupakan fakta individual yang tidak layak ditebak dari nilai nasabah lain.

### 2.3 Validasi uniqueness

Business key harus unik setelah cleaning. Contoh:

```text
nasabah                       : person_id
nasabah_bulanan               : person_id + bulan_ke
transfers                     : bulan_ke + from_id + to_id
transaksi_counterparty       : bulan_ke + company_id + counterparty_id + arah
saldo                         : company_id + bulan_ke
```

### 2.4 Validasi rentang

Rentang utama yang diperiksa:

- usia: 15–100 tahun;
- nominal transfer: tidak negatif;
- jumlah transaksi: tidak negatif;
- saldo rata-rata: tidak negatif;
- saldo akhir: tidak negatif.

Hasil validasi ditulis ke:

```text
data/processed/clean/data_quality_report.csv
```

---

## 3. Penanganan missing value

### 3.1 Usia

Kolom yang digunakan:

- `nasabah.usia_bulan1`;
- `nasabah_bulanan.usia`.

Perlakuan:

- dikonversi ke numerik;
- tidak diisi dengan mean atau median;
- tidak menggunakan `ffill()` atau `bfill()`;
- harus berada pada rentang 15–100;
- jika missing atau invalid, quality check gagal.

Alasan:

Usia tidak bisa diturunkan secara akurat dari usia nasabah lain. Mengisi usia dengan median akan membuat banyak nasabah memiliki umur buatan yang sama dan dapat memengaruhi segmentasi produk, eligibility, serta model NBO.

Generator terbaru tidak lagi menanam kerusakan usia sehingga usia tetap lengkap dan valid.

### 3.2 Atribut profil nasabah

Kolom seperti berikut tidak selalu diisi:

- `kisaran_pendapatan`;
- `pekerjaan`;
- `provinsi`;
- `channel`.

Jika missing, nilainya tetap missing dan dicatat sebagai warning.

Alasan:

Tidak semua missing dapat dipulihkan tanpa sumber lain. Untuk modeling, missing dapat diubah menjadi kategori seperti `NA` pada tahap feature engineering, bukan dipaksa menjadi nilai faktual pada layer cleaning.

#### Mengapa demografi tetap missing?

Missing pada `kisaran_pendapatan`, `pekerjaan`, `provinsi`, dan `channel` tidak diisi dengan median, modus, atau nilai paling sering karena metode tersebut dapat menciptakan informasi yang tidak pernah diamati oleh bank.

Pertimbangannya:

- `kisaran_pendapatan` merupakan informasi kategori yang sensitif dan tidak dapat disimpulkan secara valid hanya dari usia atau produk yang dimiliki;
- `pekerjaan` tidak selalu dapat ditentukan dari transaksi karena satu orang dapat memiliki lebih dari satu sumber aktivitas ekonomi;
- `provinsi` tidak boleh ditebak dari provinsi mayoritas karena akan menimbulkan bias geografis;
- `channel` adalah fakta historis tentang bagaimana rekening dibuka dan tidak dapat direkonstruksi dengan aman setelah field-nya hilang.

Mengisi semua nilai kosong dengan kategori mayoritas akan membuat data terlihat lengkap, tetapi berisiko mengubah distribusi nasabah. Contohnya, semua nasabah tanpa informasi pekerjaan dapat terlihat sebagai `Pegawai/Profesional`, padahal tidak ada bukti untuk kesimpulan tersebut.

Karena itu, missing demografi diperlakukan sebagai kondisi yang valid dan informatif:

```text
cleaning layer       : tetap NaN dan dicatat sebagai warning
feature engineering  : diubah menjadi kategori "Tidak diketahui"
modeling             : dapat ditambah flag missing bila relevan
```

Dengan pendekatan ini, model dapat membedakan antara informasi demografi yang benar-benar tersedia dan informasi yang tidak tercatat. Nilai `"Tidak diketahui"` bukan berarti kategori demografi baru, melainkan penanda bahwa bank tidak memiliki informasi tersebut.

### 3.3 Produk dan segmen bulanan

Untuk kolom produk `prod_*`:

- missing dicatat sebelum imputasi;
- nilai sebelumnya dalam nasabah yang sama digunakan terlebih dahulu;
- jika masih kosong, diisi `0`.

Untuk `segmen`:

- nilai diisi menggunakan informasi antarbulan dari nasabah yang sama.

Alasan:

Status produk berbentuk indikator kepemilikan. Jika informasi hilang di tengah panel, status periode terdekat dapat menjadi proxy praktis. Nilai `0` dipakai untuk sisa missing karena panel membutuhkan matriks produk lengkap, tetapi sebaiknya flag missing tetap dibawa ke feature engineering agar `0` tidak disamakan dengan observasi yang benar-benar terukur.

### 3.4 Jumlah transaksi

Missing `jumlah_transaksi` diisi dengan median berdasarkan pasangan:

```text
from_id + to_id
```

Jika pasangan tersebut tidak memiliki nilai valid sama sekali, fallback yang digunakan adalah `1`.

Alasan:

Jumlah transaksi adalah variabel hitungan dan biasanya lebih masuk akal diimputasi menggunakan pola pasangan transaksi yang sama daripada median global. Fallback `1` mencegah baris transaksi kehilangan makna keberadaan transaksi.

### 3.5 Saldo akhir bulan

Missing `saldo_akhir_bulan_rp` diisi menggunakan rasio median:

```python
saldo_akhir_bulan_rp = saldo_rata2_rp * median_ratio
```

Dengan:

```python
median_ratio = median(
    saldo_akhir_bulan_rp / saldo_rata2_rp
)
```

Rasio hanya dihitung dari pasangan saldo yang valid dan saldo rata-rata yang positif. Pada data generator saat ini, median ratio sekitar `1,1499`.

Alasan:

Saldo akhir bulan tidak selalu sama dengan saldo rata-rata. Generator memang membuat saldo akhir sekitar 100%–130% saldo rata-rata. Median ratio mempertahankan hubungan tersebut dengan cara yang lebih robust terhadap outlier dibanding mean ratio.

Setiap nilai yang diimputasi diberi flag:

```text
saldo_akhir_bulan_rp_diimputasi = 1
```

---

## 4. Penanganan variasi teks

Kategori distandardisasi menggunakan daftar nilai valid.

Contoh variasi yang ditangani:

```text
L, l, Laki-Laki, LAKI-LAKI  -> Laki-Laki
P, p, Perempuan             -> Perempuan
Jakarta                     -> DKI Jakarta
Jogja                       -> DI Yogyakarta
Pegawai                     -> Pegawai/Profesional
Wiraswasta                  -> Pengusaha/Wiraswasta
```

Proses standardisasi:

1. menghapus spasi di awal dan akhir;
2. mengubah pembanding menjadi lowercase;
3. memetakan nilai ke kategori canonical;
4. nilai yang tidak dikenal menjadi missing agar dapat direview.

Sektor perusahaan juga distandardisasi menggunakan daftar kode sektor pada referensi BPS.

Nama perusahaan dan counterpart dibuat menjadi `name_key` dengan:

- lowercase;
- penghapusan tanda baca;
- normalisasi spasi;
- penghapusan bentuk legal seperti `PT`, `CV`, dan `Tbk`.

Ini digunakan untuk entity resolution, bukan untuk mengubah nama tampilan asli.

---

## 5. Penanganan duplikasi

Duplikasi dihapus berdasarkan business key, bukan hanya berdasarkan kesamaan seluruh baris.

Contoh:

```python
drop_duplicates(['person_id', 'bulan_ke'])
```

digunakan untuk panel bulanan karena satu nasabah hanya boleh memiliki satu baris pada satu bulan.

Alasan:

- duplicate row dapat menggandakan nominal transaksi;
- jumlah perusahaan atau nasabah dapat terhitung lebih besar;
- agregasi saldo dan transaksi dapat bias;
- model dapat melihat satu kejadian sebagai beberapa kejadian.

Baris pertama dipertahankan setelah diurutkan atau dibaca dari sumber. Untuk data produksi, sebaiknya ditambahkan aturan memilih baris berdasarkan timestamp ekstraksi atau kualitas record.

---

## 6. Penanganan outlier nominal

Outlier nominal positif diperiksa berdasarkan median kelompok.

Untuk transfer, kelompoknya adalah pasangan:

```text
from_id + to_id
```

Untuk saldo, kelompoknya adalah:

```text
company_id
```

Jika nilai lebih dari `100 x median kelompok`, nilai dianggap sebagai salah input tiga digit nol dan dibagi 1.000.

Contoh:

```text
Rp7.953.534.000.000
-> Rp7.953.534.000
```

Alasan:

- pola x1000 memang ditanam oleh generator sebagai typo positif;
- median kelompok lebih representatif daripada median seluruh populasi;
- koreksi hanya dilakukan pada outlier positif dengan median kelompok yang valid.

Generator terbaru tidak lagi menanam nominal negatif. Ini menghindari pertanyaan apakah nilai negatif adalah kesalahan atau transaksi reversal/refund.

---

## 7. Missing struktural dari export data bank

`export.py` sengaja menyembunyikan atribut tertentu dari entitas non-nasabah.

Contoh atribut perusahaan non-nasabah yang boleh missing:

- skala;
- omzet;
- jumlah karyawan;
- peran;
- bank payroll;
- segmen Bank.

Contoh atribut person non-nasabah yang boleh missing:

- usia;
- gender;
- provinsi;
- pekerjaan;
- pendapatan.

Missing ini bukan kerusakan data. Nilai tersebut memang tidak terlihat oleh bank dan tidak boleh diisi menggunakan data truth.

---

## 8. Output cleaning

Hasil cleaning disimpan sebagai Parquet di:

```text
data/processed/clean/
```

Contoh output:

```text
nasabah.parquet
nasabah_bulanan.parquet
companies.parquet
persons.parquet
transfers.parquet
saldo.parquet
transaksi_counterparty.parquet
lead_bisdev.parquet
data_quality_report.csv
```

Evaluasi terhadap data truth disimpan oleh pipeline di:

```text
outputs/cleaning_report.csv
```

---

## 9. Perbedaan dengan `clean.py` awal

| Aspek | Versi awal | Versi sekarang |
|---|---|---|
| Usia nasabah | Nilai invalid diubah menjadi `NaN` | Usia dikonversi ke numerik, tidak diimputasi, dan wajib valid |
| Usia panel bulanan | Invalid diubah menjadi `NaN`, lalu `ffill/bfill` | Tidak ada imputasi usia |
| Saldo akhir missing | Menggunakan median ratio secara langsung | Tetap menggunakan median ratio, tetapi ratio hanya dari pasangan valid dan hasil diberi flag |
| Flag imputasi saldo | Tidak tersedia | `saldo_akhir_bulan_rp_diimputasi` |
| Saldo akhir negatif | Belum ada validasi rentang eksplisit | Diperiksa agar tidak negatif setelah cleaning |
| Schema check | Belum lengkap | Kolom wajib divalidasi |
| Critical null check | Terbatas pada identifier | Identifier dan usia nasabah divalidasi |
| Unique key check | Sebagian dilakukan saat cleaning | Diperiksa ulang oleh quality validation |
| Range check | Terbatas | Usia, transfer, jumlah transaksi, dan saldo diperiksa |
| Quality report | Belum konsisten | Ditulis ke `data_quality_report.csv` |
| Data generator | Usia dapat dikotori | Usia dijaga lengkap dan valid oleh generator terbaru |
| Nominal negatif | Berpotensi dikoreksi dengan `abs()` | Tidak lagi ditanam oleh generator |

Perubahan paling penting adalah tidak lagi melakukan imputasi usia. Versi awal membuat data tampak lengkap, tetapi tidak memiliki dasar bisnis untuk menentukan umur pengganti. Versi sekarang lebih konsisten dengan prinsip data bank-visible: nilai yang tidak diketahui tidak boleh dibuat seolah-olah diketahui.

---

## 10. Catatan keterbatasan

Beberapa aturan masih merupakan kebijakan untuk data sintetis dan perlu disesuaikan jika digunakan pada data produksi:

- threshold outlier `100 x median` perlu dikalibrasi pada data aktual;
- fallback `jumlah_transaksi = 1` perlu dikonfirmasi dengan definisi transaksi;
- imputasi saldo dengan median ratio mengasumsikan hubungan saldo akhir dan saldo rata-rata stabil;
- `ffill/bfill` pada produk dan segmen dapat menyamarkan perubahan status jika flag tidak dibawa ke model;
- nilai missing kategorikal tetap membutuhkan kebijakan eksplisit saat feature engineering.

Cleaning harus dipandang sebagai proses yang dapat diaudit, bukan proses untuk memaksa seluruh dataset terlihat sempurna.
