# Generator Data Sintetis — RM Copilot NBO + Value Chain + Wholesale

Folder ini berdiri sendiri: salin ke folder project baru, pasang library, jalankan satu perintah. Hasilnya semua data yang dibutuhkan PRD dan Guideline Data Sintetis, 100% sintetis, tanpa PII, dan dicek otomatis terhadap data resmi.

## Cara pakai

```
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python run.py                  # ukuran penuh dari config.yaml (50 ribu nasabah, ~2-3 menit)
python run.py --nasabah 5000   # cepat, untuk mencoba
```

Hasil ada di `output/`, termasuk `validation_report.md`. Seed tetap, jadi hasilnya selalu sama selama `config.yaml` tidak diubah.

## Prinsip: tidak ada angka tanpa asal-usul

| Jenis angka | Disimpan di | Contoh |
| --- | --- | --- |
| Data resmi Indonesia | `reference/` (sumber di `reference/SUMBER.md`) | Penduduk BPS 2026, upah BPS Agustus 2025, SNLIK 2025, AKKI, LPS |
| Aturan produk Bank | `reference/produk_model.csv`, dari katalog | Tabungan Plus Muda 17-35 tahun, Fleksi untuk pegawai |
| Perilaku bulanan nyata (rujukan bentuk saja) | `reference/*_santander.csv`, dari `calibrate/` | Laju tutup produk per bulan; dipakai hanya bila tidak ada data Indonesia |
| Hasil interview RM dan PS Bank | `config.yaml` bagian `wholesale`, ditandai "interview" | Segmen Commercial Rp10-150 M, 40 debitur + 15 non-debitur per RM |
| Asumsi tim (tidak ada data publik) | `config.yaml`, diberi label ASUMSI | Porsi perusahaan Bank, koefisien label akuisisi |

## Apa yang dihasilkan

Output dibagi dua folder supaya tim tidak memakai data yang di dunia nyata tidak dimiliki bank. Aturannya ada di `kamus_data.csv` (status HIJAU/KUNING/ORANYE/MERAH per kolom, sumber nyatanya, dan boleh tidaknya jadi fitur model).

**`output/data_bank/` — dipakai tim model, app, dan dashboard**

| File | Satu baris = | Isi |
| --- | --- | --- |
| `nasabah.csv` | satu nasabah Bank | Data KYC: umur, jenis kelamin, provinsi, desa/kota, pekerjaan, **kisaran** pendapatan, channel, bulan masuk/keluar |
| `nasabah_bulanan.parquet` | satu nasabah per bulan (17 bulan) | Mesin NBO: kepemilikan 15 produk Bank (`prod_*`), segmen, aktif, lama menjadi nasabah |
| `produk_level.csv` | satu produk | Level kepemilikan target dan sumbernya |
| `persons.csv` | satu orang yang terlihat bank | Nasabah: data KYC. Non-nasabah: hanya ID dan bank penerima (kolom demografi kosong) |
| `companies.csv` | satu perusahaan yang terlihat bank | Nasabah: data lengkap. Non-nasabah: sektor/provinsi/tahun berdiri (registry publik); skala, omzet, karyawan kosong |
| `employment.csv` | satu hubungan kerja/kepemilikan yang terlihat bank | Karyawan nasabah, karyawan yang digaji dari rekening Bank, pemilik perusahaan nasabah |
| `transfers_monthly.csv` | satu pasangan pengirim-penerima per bulan | Hanya transfer yang salah satu sisinya nasabah Bank |
| `acquisitions.csv` | satu non-nasabah yang terlihat bank | Label akuisisi: bulan dan tanggal jadi nasabah, produk pertama, anchor penghubung |
| `rm_portofolio.csv` | satu perusahaan kelolaan RM | RM, cabang, segmen, status debitur di bulan 1 |
| `transaksi_counterparty_bulanan.csv` | nasabah x counterpart x bulan x arah | Nama dan bank lawan transaksi, channel (BI-FAST/SKN/RTGS/pemindahbukuan), klasifikasi nama x bank |
| `saldo_bulanan.csv` | satu nasabah korporasi per bulan | Saldo rata-rata dan saldo akhir bulan |
| `riwayat_produk_wholesale.csv` | satu pemakaian produk | Produk katalog, tanggal mulai/selesai, status, beneficiary, nilai proyek |
| `fasilitas_pembiayaan.csv` | satu fasilitas | KMK, KI, Supply Chain Financing: plafon, baki debet, jatuh tempo |
| `lead_bisdev.csv` | satu lead | Meniru Excel Bisdev: sering hanya nama, tanpa company_id |
| `label_wholesale.csv` | satu kejadian | non_debitur_ke_debitur, cross_sell_wholesale, reaktivasi, leakage (bulan 12-17) |
| `kamus_data.csv` | satu kolom | Ketersediaan di dunia nyata dan boleh tidaknya jadi fitur |

**`output/kunci_evaluasi/` — kebenaran lengkap, hanya untuk evaluasi**

Versi lengkap semua file (`*_lengkap.csv`): pendapatan pasti, demografi prospek, omzet dan karyawan semua perusahaan, transfer antar pihak non-nasabah, kandidat yang tidak terlihat bank, plus `relationship_truth.csv`, `lead_bisdev_kunci.csv` (lead ke company_id), dan `counterparty_pindah_bank.csv`. Jangan dipakai sebagai fitur model.

**`output/`**: `validation_report.md` (52 cek lolos/gagal + 4 baris INFO pembanding Santander) dan `config_terpakai.yaml`.

### Data kotor terkontrol (untuk EDA)

`data_bank/` sengaja berisi masalah kualitas data yang biasa ada di ekstrak bank, supaya tim punya pembersihan nyata untuk rubrik EDA Hari 2:

| Jenis | Contoh |
| --- | --- |
| Nilai hilang | kisaran pendapatan, pekerjaan, provinsi, channel, flag produk, segmen, jumlah transaksi, tahun berdiri |
| Variasi teks | `JAWA BARAT`, `jawa barat`, spasi di awal/akhir, singkatan (`L`, `P`, `Jakarta`, `Jogja`, `Pegawai`); nama perusahaan `PT. Mitra 0001`, `MITRA 0001 PT`, `Mitra 0001` |
| Outlier | usia -1, 0, 150, 999; nominal transfer x1000 atau bernilai negatif |
| Duplikat baris | nasabah, data bulanan, transfer, transaksi counterparty, lead Bisdev |

Porsinya diatur di `config.yaml` (`data_kotor`, label ASUMSI; `aktif: false` untuk data bersih). `kunci_evaluasi/` tetap bersih, dan setiap perubahan dicatat di `kunci_evaluasi/catatan_data_kotor.csv` (file, kolom, jenis, id, nilai asli, nilai kotor) sebagai kunci jawaban pembersihan.

Kalender: `bulan_ke` 1-17 = Januari 2025 sampai Mei 2026.

## Cara datanya dibuat

1. **Penduduk 15-79 tahun.** Umur x jenis kelamin dari BPS, disesuaikan ke total per kelompok umur SNLIK. Provinsi dari proyeksi BPS 2026. Pekerjaan dicocokkan ke sebaran SNLIK (IPF, dengan batas umur pelajar dan pensiunan).
2. **Pendapatan.** Pegawai: distribusi upah BPS Agustus 2025 per provinsi x jenis kelamin (log-normal yang di-fit ke 8 kelompok upah). Pekerja lain: sisa distribusi pendapatan SNLIK setelah porsi pegawai dikurangi. Pelajar, ibu rumah tangga, dan yang belum bekerja: tanpa pendapatan sendiri (36,0%, sama dengan SNLIK).
3. **Siapa punya rekening bank.** Model logit yang diselaraskan sehingga inklusi per umur, desa/kota, gender, pekerjaan, dan pendapatan sama dengan SNLIK (diskalakan ke sektor perbankan 70,65%). Nasabah Bank dipilih dari yang punya rekening.
4. **Produk Bank.** Rekening utama mengikuti aturan katalog (Tabungan Plus Anak, Tabungan Plus Muda, Tabungan Plus). Produk lain: level dari AKKI/SNLIK/LPS/mobile banking bila ada; bentuk menurut umur, pendapatan, dan korelasi antar produk dari Santander; kelayakan dari katalog.
5. **Pergerakan bulanan.** Penutupan produk mengikuti laju nyata Santander; pembukaan dihitung agar level tetap stabil. Nasabah masuk dan keluar dengan laju median Santander. Umur bertambah tiap bulan, jadi rekening utama berganti sesuai aturan katalog.
6. **Value chain.** 50 anchor (nasabah korporasi Bank) dan 20.000 mitra, plus sekitar 6.500 pedagang perorangan yang membeli dari distributor/anchor Bank; sektor dari BPS, omzet dari PP 7/2021, jumlah karyawan dari klasifikasi BPS. Mitra memilih anchor dengan bobot Pareto, sehingga derajatnya long tail. Ada sub-supplier (relasi 2 langkah).
7. **Transfer.** Pembayaran B2B sebanding dengan omzet pihak yang lebih kecil, dengan noise bulanan dan efek Lebaran untuk sektor dagang dan makan-minum. Payroll = pendapatan karyawan, dan **THR 1x upah di bulan Idul Fitri**.
8. **Konsistensi.** Nasabah yang pernah memegang Bank Payroll bekerja di perusahaan dengan payroll Bank, dan sebaliknya.
9. **Label akuisisi.** Rumus yang diketahui (Guideline bagian 6): nominal dengan entitas Bank, porsi tetangga Bank, lama relasi, skala, sektor, efek menular dari mitra yang baru bergabung, dan noise. Base rate dikalibrasi ke 4%. Dua jendela walk-forward: validasi (fitur bulan 1-5, label 6-11) dan test (fitur 1-11, label 12-17); base rate 4% per jendela.
10. **Wholesale** (interview RM dan PS, Guideline bagian 14). Segmen dari omzet; RM memegang 55 perusahaan Commercial/Corporate (sekitar 40 debitur). Transaksi dilihat dari sisi nasabah Bank, plus pemindahan ke rekening sendiri di Bank atau bank lain; channel mengikuti batas Bank Indonesia. Riwayat produk memakai nama dan nomor katalog, dipicu kebutuhan (sektor, banyak pembayar, saldo, kontraktor). KMK/KI hanya untuk usaha >= 3 tahun (katalog). UMKM memakai QRIS/EDC dan KUR (katalog no. 207, 199, 108, 109). Label wholesale di dua jendela yang sama, base rate dari proksi publik (SUMBER.md), minimal 100 label per jendela.

## Validasi yang dijalankan

`validation_report.md` mencakup 43 cek, antara lain: sebaran umur/gender/pekerjaan/pendapatan vs SNLIK, upah pegawai vs BPS (termasuk profil upah naik dengan umur per jenis kelamin), pemegang Reksa Dana dan Bonds per umur dan penghasilan vs KSEI Okt 2025, kepemilikan deposito/giro/Prioritas/kartu kredit naik dengan penghasilan, inklusi per karakteristik vs SNLIK, level produk vs target, degree long tail, nominal per skala, lonjakan THR, aturan konsistensi, kepatuhan (syarat produk, kartu kredit BI PADG 32/2025: 21+ dan pendapatan >= Rp3 juta, nasabah < 17 tahun), base rate, "sinyal graph lebih kuat dari tabel" (hanya fitur yang terlihat bank), dan realisme data_bank (transfer selalu punya sisi Bank, kolom MERAH kosong untuk non-nasabah), jumlah data kotor yang ditanam sesuai config, serta data wholesale (batas channel BI, fasilitas hanya debitur, KMK/KI >= 3 tahun, tanggal produk konsisten, produk ada di katalog, debitur per RM, kontak hanya ber-CIF, label hanya di jendela label, AUC label wholesale 0,55-0,95). Churn, pola kepemilikan bersama, dan arus nasabah dibandingkan dengan Santander sebagai INFO saja, tidak menentukan lolos/gagal: Santander adalah data ritel Spanyol 2015-2016, jauh lebih sempit dari segmen Bank.

## Keterbatasan (sebut terbuka di presentasi)

- **Bukan data Bank.** Level produk adalah angka nasional (AKKI, SNLIK, LPS) yang diasumsikan berlaku untuk nasabah Bank. Profil nasabah Bank per umur/provinsi tidak dipublikasikan.
- **Santander hanya rujukan bentuk** (ritel Spanyol 2015-2016): laju tutup produk dan korelasi antar produk, karena belum ada panel bulanan Indonesia. Pengaruh umur dan penghasilan untuk reksa dana, obligasi, deposito, giro, Prioritas, dan kartu kredit sudah memakai data Indonesia (KSEI) atau asumsi tim. Santander tidak punya segmen korporasi; semua data wholesale dibuat dari katalog Bank, aturan BI, dan interview.
- **Beberapa level tanpa data Indonesia** (KPR, KTA, payroll, autodebit, prioritas) memakai level Santander; lihat `produk_level.csv`.
- **Giro dan Deposito** memakai porsi rekening non-tabungan LPS, yang juga mencakup rekening badan usaha, jadi levelnya batas atas.
- **Distribusi upah** di-fit dengan log-normal; bentuknya meleset rata-rata ~5 poin persen per kelompok (terutama upah rendah).
- **Struktur umur dan porsi perkotaan** dianggap sama di semua provinsi.
- **Value chain, data wholesale, dan semua label** sepenuhnya dari asumsi, interview, dan rumus; hasil model membuktikan metode, bukan perilaku pasar.
- **Batas segmen dan ukuran portofolio RM** dari satu interview dan belum final.
- Koefisien label di `config.yaml` sebaiknya tidak dibuka oleh pembuat model sampai evaluasi selesai.

## Kalibrasi ulang (opsional)

File `reference/*_santander.csv` sudah tersedia. Untuk membuat ulang dari data Santander asli:

```
python calibrate/dinamika_santander.py --train path/ke/train.csv --sample 200000
```
