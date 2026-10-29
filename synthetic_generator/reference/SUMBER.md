# Sumber data rujukan

Semua angka yang dipakai generator berasal dari file di folder ini. Angka yang tidak punya sumber publik ada di `config.yaml` dan diberi label ASUMSI.

## Sumber resmi Indonesia

| File | Isi | Sumber | Diambil |
| --- | --- | --- | --- |
| bps_penduduk_provinsi_2026.csv | Penduduk 38 provinsi (ribu jiwa), total 287,2 juta | BPS, tabel "Jumlah Penduduk ... Menurut Provinsi, 2026", proyeksi SP2020 pertengahan tahun. https://www.bps.go.id/id/statistics-table/3/V1ZSbFRUY3lTbFpEYTNsVWNGcDZjek53YkhsNFFUMDkjMyMwMDAw/ (year=2026) | 8 Okt 2026 |
| bps_penduduk_umur_jk_2025.csv | Penduduk per kelompok umur 5 tahunan x jenis kelamin (ribu), total 284,4 juta | BPS, tabel "Population by Age Groups and Sex", 2025. https://www.bps.go.id/id/statistics-table/3/WVc0MGEyMXBkVFUxY25KeE9HdDZkbTQzWkVkb1p6MDkjMyMwMDAw/ (year=2025; tahun 2026 belum dapat diakses) | 8 Okt 2026 |
| bps_upah_kelompok_2025.csv | Jumlah pekerja per 8 kelompok upah x 38 provinsi x jenis kelamin, plus rata-rata upah | BPS, publikasi "Keadaan Pekerja di Indonesia Agustus 2025" (terbit 23 Des 2025): hal. 133, 136, 137 (kelompok upah) dan hal. 24, 27, 28 (rata-rata). https://www.bps.go.id/id/publication/2025/12/23/5fe58c9723acafc73fb95bff/ | 8 Okt 2026 |
| bps_upah_lognormal_2025.csv | Parameter log-normal per provinsi x jenis kelamin, di-fit ke 8 kelompok upah dan rata-rata BPS | Dihitung dari bps_upah_kelompok_2025.csv. Rata-rata model selisih < 0,5% dari BPS | 8 Okt 2026 |
| bps_upah_umur_2025.csv | Rata-rata upah/gaji bersih sebulan buruh/karyawan/pegawai per kelompok umur x jenis kelamin (bentuk upah naik dengan umur, turun setelah 55-59) | Publikasi BPS yang sama, Tabel 4.41 hal. 303 (total), Tabel 4.44 hal. 315 (laki-laki), Tabel 4.45 hal. 319 (perempuan), kolom Jumlah/Total. Generator memakai rasio per umur terhadap rata-rata, jadi rata-rata provinsi tetap dari bps_upah_kelompok_2025.csv | 9 Okt 2026 |
| bps_pekerja_sektor_2025.csv | Jumlah pekerja per 17 lapangan usaha, total 70.816.265 | Publikasi BPS yang sama, Tabel 3.37 hal. 113-114 | 8 Okt 2026 |
| ojk_snlik_2025_profil.csv | Penduduk 15-79 tahun (213,8 juta) per desa/kota, gender, umur, pekerjaan, pendapatan | OJK-BPS, Buku Statistik SNLIK 2025, Lampiran 1 dan Tabel 4.2. Baris "Tidak ada kegiatan ekonomi" = 213,829 dikurangi jumlah kelompok pendapatan. https://www.ojk.go.id/id/Fungsi-Utama/Perilaku-Pelaku-Usaha-Jasa-Keuangan/SNLIK/Documents/Buku%20Statistik%20Survei%20Nasional%20Literasi%20dan%20Inklusi%20Keuangan%20%28SNLIK%29%20Tahun%202025.pdf | 8 Okt 2026 |
| ojk_snlik_2025_inklusi.csv | Indeks inklusi keuangan (komposit) per karakteristik dan per sektor | SNLIK 2025 Lampiran 18 dan 20 (judul lampiran tertulis "Tahun 2024", isinya hasil SNLIK 2025: nasional 80,51%) | 8 Okt 2026 |
| ksei_investor_2025.csv | Porsi investor individu per kelompok umur dan per penghasilan tahunan (Okt 2025). Dipakai sebagai bentuk siapa yang memegang Reksa Dana dan Bonds | KSEI, Statistik Publik Oktober 2025, hal. 6 "Demografi Investor Individu (2/2)". https://web.ksei.co.id/files/Statistik_Publik_Oktober_2025.pdf | 9 Okt 2026 |
| (config.yaml: wholesale.batas_*) | Batas nominal channel per transaksi: BI-FAST sampai Rp250 juta, SKNBI sampai Rp1 miliar, RTGS di atas Rp100 juta | Bank Indonesia, dirangkum detikFinance "BI Fast Adalah: Kenali Manfaat serta Bedanya dengan RTO, RTGS, dan SKNBI". https://finance.detik.com/moneter/d-6817089/bi-fast-adalah-kenali-manfaat-serta-bedanya-dengan-rto-rtgs-dan-sknbi | 9 Okt 2026 |
| (config.yaml: wholesale) | Segmen RCC < Rp10 M dan Commercial Rp10-150 M, 40 debitur + 15 non-debitur per RM, file lead Bisdev sering hanya nama, klasifikasi nama x bank | Interview RM Transactional dan Product Specialist Bank, Okt 2026 (catatan gabungan tim); belum final, perlu validasi | 9 Okt 2026 |
| (config.yaml: wholesale.label) | Proksi base rate label wholesale per 6 bulan: pengguna CIB cash 261.815 per Des 2025, naik 24,8% setahun (cross-sell); kredit korporasi Bank +10,4% YoY S1 2025 dan kredit investasi nasional +17,98% YoY Nov 2025 (non-debitur ke debitur) | Bisnis.com  ; Investortrust  ; IDX Channel https://www.idxchannel.com/banking/kredit-perbankan-november-2025-capai-rp8314-triliun-tumbuh-774-persen/all | 9 Okt 2026 |
| (config.yaml: wholesale KUR dan produk_umkm) | KUR Bank Rp10,6 triliun ke sekitar 46 ribu UMKM per Okt 2025; 39,3 juta merchant QRIS per semester I 2025 | Kontan  ; Kontan https://keuangan.kontan.co.id/news/bi-sebut-pengguna-qris-tembus-57-juta-orang-per-semester-i-2025 | 9 Okt 2026 |
| kalender_2025_2026.csv | Bulan ke-1..17 dan bulan pembayaran THR | Idul Fitri 1446 H = 31 Mar 2025 dan 1447 H = 21 Mar 2026 (SKB 3 Menteri); THR dibayar paling lambat 7 hari sebelum hari raya (Permenaker 6/2016) | 8 Okt 2026 |
| indikator_publik.csv | Kartu kredit beredar (AKKI), rekening simpanan (LPS), pengguna mobile banking (Bank), batas omzet (PP 7/2021), batas tenaga kerja (BPS) | Lihat kolom sumber di file | 8 Okt 2026 |
| produk_bank_knowledge.csv | Katalog 216 produk Bank | Hasil scrape tim dari bank.co.id (kolom URL_Sumber) | - |
| produk_model.csv | 15 produk ritel yang disimulasikan, aturan kelayakan, cara menentukan level | Nama dan aturan dari katalog (kolom sumber_aturan) | - |

## Data nyata yang dipakai untuk bentuk perilaku (bukan level)

Tidak ada data publik Indonesia tentang pergerakan produk per nasabah per bulan. Bentuknya diukur dari panel nyata Santander (Kaggle Santander Product Recommendation, 200 ribu nasabah sampel, 17 bulan) dengan `calibrate/dinamika_santander.py`:

| File | Isi |
| --- | --- |
| dinamika_produk_santander.csv | Level, laju pembukaan dan penutupan bulanan per produk |
| rr_umur_santander.csv | Rasio kepemilikan per kelompok umur (kelompok umur SNLIK) |
| rr_pendapatan_santander.csv | Rasio kepemilikan per kuintil pendapatan di dalam provinsi |
| korelasi_produk_santander.csv | Korelasi laten antar produk (pendekatan tetrachoric) |
| dinamika_nasabah_santander.csv | Nasabah masuk dan keluar per bulan |
| santander_tambahan.csv | Median laju masuk/keluar, porsi segmen TOP, kuantil lama menjadi nasabah |

Catatan: satu bulan di Santander (2015-07) menambah sekitar 23% nasabah sekaligus; ini perluasan panel di data sumber, sehingga generator memakai median bulanan.
