# Guideline Data Sintetis — Nasabah dan Value Chain

Oct 8, 2026 · @Firgy Matannatikka

## 1. Tujuan

Guideline ini menjelaskan semua data sintetis project: nasabah Bank dengan kepemilikan produk bulanan (untuk mesin NBO) dan value chain di sekitar nasabah bisnis (untuk mesin akuisisi). Tim memutuskan full sintetis karena data Santander tidak mencerminkan konteks, produk, dan relasi nasabah Indonesia, dan data internal bank dilarang aturan capstone.

Generator sudah dibuat di folder synthetic\_generator: satu perintah (python run.py) membangkitkan semua data plus laporan validasi. Angka dikalibrasi ke data resmi (BPS, OJK SNLIK 2025, KSEI, AKKI, LPS, Bank Indonesia, katalog Bank) dan interview RM/PS; Santander hanya rujukan bentuk untuk laju buka-tutup produk dan korelasi antar produk. Semua asumsi tim ada di config.yaml dengan label ASUMSI.

Bagian berikut tetap menjelaskan konsep value chain, karena itulah alasan utama data relasi perlu dibuat.

**Konsep value chain acquisition.** Sebuah perusahaan nasabah (disebut anchor) rutin membayar supplier, menerima pembayaran dari distributor, dan menggaji karyawan. Banyak dari lawan pihak itu memakai bank lain. Aliran transfer dari dan ke anchor memperlihatkan siapa mereka, seberapa kuat hubungannya, dan seberapa layak mereka didekati.

**Pertanyaan bisnis yang dijawab**

- Siapa saja non-nasabah yang paling sering dan paling besar bertransaksi dengan nasabah Bank?
- Mana yang paling mungkin bersedia membuka rekening, dan produk apa yang cocok untuk mereka?
- Anchor mana yang menjadi pintu masuk paling efektif untuk akuisisi satu ekosistem sekaligus?

**Output untuk RM:** daftar prospek berperingkat, beserta anchor penghubungnya, alasan (jalur di graph), dan produk pembuka yang disarankan. Daftar ini masuk ke alur yang sama dengan NBO: guardrail, reasoning AI, dan persetujuan RM.

## 2. Kenapa knowledge graph

Calon nasabah value chain hampir tidak punya data di bank: tidak ada profil, tidak ada riwayat produk. Satu-satunya yang kita tahu tentang mereka adalah hubungan mereka dengan nasabah kita. Data tabel menyimpan baris, sedangkan graph menyimpan hubungan, jadi untuk masalah ini graph bukan tambahan, melainkan satu-satunya cara melihat prospeknya.

| Kebutuhan | Dengan tabel biasa | Dengan knowledge graph |
| --- | --- | --- |
| Menemukan prospek 2 langkah jauhnya (anchor ke supplier ke sub-supplier) | Join berulang, lambat, mudah salah | Satu query jalur |
| Menilai pengaruh sebuah entitas di ekosistem | Hanya bisa menghitung jumlah transaksi langsung | PageRank dan centrality memperhitungkan seluruh jaringan |
| Menemukan klaster bisnis (rantai pasok satu industri) | Butuh label industri yang mungkin tidak ada | Community detection (Louvain) menemukannya dari pola transaksi |
| Memprediksi siapa yang akan menjadi nasabah | Fitur prospek hampir kosong | Link prediction: fitur diambil dari tetangganya |
| Menjelaskan rekomendasi ke RM | Skor tanpa konteks | Jalur yang bisa ditunjuk: "CV X menerima Rp 1,2 miliar per bulan dari anchor PT Y" |
| Menambah sumber data baru | Ubah skema tabel | Tambah node atau relasi baru |

**Kalimat untuk penguji:** "Prospek value chain tidak punya data, yang ada hanya hubungan. Knowledge graph membuat hubungan itu bisa dihitung, dijelaskan, dan diprioritaskan."

Kaitan dengan rubrik: guideline capstone menyebut graph analytics (analisis ecosystem, entitas berpengaruh, community detection, link prediction) sebagai faktor pembeda. Fitur ini memakai keempatnya sekaligus, ditambah link prediction yang sudah ada di NBO.

## 3. Skema graph

Semua data membentuk satu graph. Node Person menjadi jembatannya: nasabah Bank yang punya riwayat produk bulanan (mesin NBO) bisa juga bekerja di atau memiliki perusahaan di value chain (mesin akuisisi), dengan person\_id yang sama.

&#91;embedded content: skema graph gabungan · 8 jenis node\]

Panah menunjukkan arah relasi; nama di dalam kotak adalah nama relasi yang menuju node itu. Panah dari Person ke Company adalah WORKS\_AT. Person juga bisa memiliki Company (OWNS), dan Company yang sudah nasabah Bank juga memiliki Product. Kedua relasi ini tidak digambar supaya diagram tetap terbaca.

## 4. Kamus data

Generator menulis 15 file data plus kamus\_data.csv ke synthetic\_generator/output/data\_bank (versi lengkap di kunci\_evaluasi). Tabel di bawah adalah 9 file sisi nasabah dan value chain; 7 file wholesale ada di bagian 14. Semua nama dan ID buatan; tidak ada nama asli, NIK, nomor rekening, atau alamat. Kalender: bulan\_ke 1 sampai 17 = Januari 2025 sampai Mei 2026.

| File | Satu baris = | Kolom utama |
| --- | --- | --- |
| nasabah.csv | satu nasabah Bank | person\_id, usia\_bulan1, jenis\_kelamin, provinsi, perkotaan, pekerjaan, pendapatan\_bulanan\_idr, bulan\_masuk, bulan\_keluar, lama\_nasabah\_bulan\_saat\_masuk\_panel, channel |
| nasabah\_bulanan.parquet | satu nasabah per bulan | person\_id, bulan\_ke, bulan, usia, 15 kolom prod\_\* (0/1), aktif, segmen, lama\_nasabah\_bulan |
| produk\_level.csv | satu produk | produk, kolom, level\_target, sumber\_level, analog\_santander |
| persons.csv | satu orang | person\_id, usia, jenis\_kelamin, provinsi, perkotaan, pekerjaan, pendapatan\_bulanan\_idr, is\_bank\_customer, bank\_utama, bank\_payroll |
| companies.csv | satu perusahaan | company\_id, is\_anchor, sektor (KBLI), provinsi, skala, peran, nama\_samaran, omzet\_tahunan\_rp, jumlah\_karyawan, tahun\_berdiri, bank\_utama, bank\_payroll, is\_bank\_customer, produk\_bank |
| employment.csv | satu hubungan kerja atau kepemilikan | person\_id, peran (KARYAWAN/PEMILIK), company\_id, bulan\_mulai, bulan\_selesai |
| transfers\_monthly.csv | satu pasangan pengirim-penerima per bulan | bulan\_ke, bulan, from\_id, to\_id, jenis\_relasi\_terlihat, total\_nominal\_rp, jumlah\_transaksi |
| relationship\_truth.csv | satu relasi | from\_id, to\_id, jenis\_relasi\_asli, bulan\_mulai, bulan\_selesai (hanya untuk evaluasi) |
| acquisitions.csv | satu non-nasabah | entity\_id, tipe, bulan\_jadi\_nasabah (0 = tidak), tanggal\_jadi\_nasabah, produk\_pertama, via\_anchor\_id |

**15 produk Bank yang disimulasikan** (nama persis dari katalog): Tabungan Plus, Tabungan Plus Muda, Tabungan Plus Anak (rekening utama, menurut aturan umur katalog), Bank Giro, Bank Deposito, Mobile Banking, Bank Payroll, Bank Visa Platinum, KPR Pembelian, Bank Fleksi, DPLK Pensiun, Reksa Dana (agen penjual), Bonds, Autodebit, Prioritas. Produk perusahaan: Tabungan Plus Bisnis, Bank Giro (Non Perorangan), CIB, CIB Supply Chain (anchor), Payroll Korporasi.

**Nilai kategori**

- pekerjaan: 8 kategori SNLIK (Pegawai/Profesional, Pengusaha/Wiraswasta, Pensiunan/Purnawirawan, Petani/Peternak/Pekebun/Nelayan, Pekerjaan Lainnya, Pelajar/Mahasiswa, Ibu Rumah Tangga, Tidak/Belum Pernah Bekerja)
- segmen: Prioritas (pemegang Prioritas), Pelajar dan Mahasiswa, Ritel
- channel: Kantor Cabang, Agen Bank, Mobile Banking, Payroll Korporasi
- skala: Mikro, Kecil, Menengah, Besar; peran: ANCHOR, SUPPLIER, DISTRIBUTOR, LAINNYA
- jenis\_relasi\_terlihat: SUPPLIER, DISTRIBUTOR, LAINNYA, PAYROLL, atau UNKNOWN (sengaja disamarkan)
- bank: Bank, BANK\_A, BANK\_B, BANK\_C, atau TIDAK ADA

## 5. Ukuran dan distribusi data

Ukuran default menghasilkan sekitar 56 ribu nasabah, 86 ribu orang, dan 20.050 perusahaan dalam sekitar 130 detik di laptop. Ukuran bisa diubah di config.yaml; setiap distribusi di bawah punya sumber atau label ASUMSI.

**Ukuran (default)**

| Komponen | Hasil run penuh | Catatan |
| --- | --- | --- |
| Nasabah Bank | 50.000 di bulan 1, 55.928 total selama 17 bulan | Ada yang masuk dan keluar tiap bulan |
| Baris bulanan nasabah | 886.639 |  |
| Perusahaan | 50 anchor + 20.000 mitra |  |
| Orang di persons.csv | 85.932 | Semua nasabah + 12.000 prospek karyawan + 6.478 pedagang + pemilik usaha |
| Baris transfer | 856.640 | B2B, payroll, dan pembelian pedagang |
| Kandidat akuisisi | 44.955 | Perusahaan dan orang yang belum nasabah Bank |

**Distribusi dan sumbernya**

| Variabel | Cara dibangkitkan | Sumber |
| --- | --- | --- |
| Umur x jenis kelamin | Kelompok 5 tahunan BPS, disesuaikan ke total kelompok umur SNLIK | BPS 2025, SNLIK 2025 |
| Provinsi | Proporsional penduduk | BPS proyeksi 2026 |
| Desa/kota | 60,77% perkotaan | SNLIK 2025 |
| Pekerjaan | IPF ke sebaran SNLIK, dengan batas umur pelajar dan pensiunan | SNLIK 2025; batas umur ASUMSI |
| Pendapatan pegawai | Log-normal per provinsi x jenis kelamin, di-fit ke 8 kelompok upah | BPS Keadaan Pekerja Agustus 2025 |
| Pendapatan pekerja lain | Sisa distribusi pendapatan SNLIK setelah porsi pegawai | SNLIK 2025 + BPS |
| Punya rekening bank | Logit yang diselaraskan ke inklusi per umur, desa/kota, gender, pekerjaan, pendapatan | SNLIK 2025 (diskalakan ke perbankan 70,65%) |
| Level produk | Kartu kredit, dana pensiun, pasar modal, rekening, mobile banking; produk lain dari Santander | AKKI, SNLIK, LPS, Bank; lihat produk\_level.csv |
| Korelasi antar produk dan laju tutup bulanan; pengaruh umur dan pendapatan hanya untuk produk tanpa data Indonesia | Rujukan bentuk dari panel nyata (dibandingkan sebagai INFO) | Santander (calibrate/dinamika\_santander.py) |
| Arus nasabah | Masuk 0,72% dan keluar 0,18% per bulan (INFO) | Median Santander |
| Sektor perusahaan | Proporsional pekerja per lapangan usaha (tanpa administrasi pemerintahan) | BPS Agustus 2025 |
| Omzet dan karyawan | Batas omzet per skala; batas karyawan per skala; ekor Pareto usaha besar | PP 7/2021, klasifikasi BPS; ekor ASUMSI |
| Jumlah relasi per anchor | Bobot Pareto, menghasilkan long tail | ASUMSI |
| Nominal transfer B2B | Porsi omzet pihak yang lebih kecil, noise bulanan sekitar 15% | ASUMSI |
| Musiman | Payroll + THR 1x upah di bulan Idul Fitri; transfer sektor dagang dan makan-minum naik 15% | SKB 3 Menteri, Permenaker 6/2016; besaran sektor ASUMSI |

**Ambiguitas yang sengaja ditanam** (menjawab pitfall low signal)

- Sekitar 30% jenis\_relasi\_terlihat dibuat UNKNOWN.
- Nominal B2B bervariasi tiap bulan dan sebagian relasi mulai atau berhenti di tengah periode.
- Label akuisisi mengandung noise acak per entitas.

## 6. Sinyal yang ditanam dan label akuisisi

Pembaruan: label dibangkitkan dari kondisi sebenarnya (termasuk skala usaha yang tidak terlihat bank), sedangkan fitur model hanya dihitung dari transfer yang terlihat bank. Sinyal tambahan "porsi Bank dua langkah" (rekan kerja yang digaji ke Bank, atau mitra lain dari anchor yang sama) ikut ditanam karena di dunia nyata inilah sinyal terkuat untuk prospek perorangan.

Peluang sebuah non-nasabah menjadi nasabah dibangkitkan dari rumus yang diketahui. Sebagian besar sinyalnya berasal dari jaringan, sebagian kecil dari atribut tabel. Dengan begitu uji ablasi "graph vs tanpa graph" punya jawaban yang bisa dibuktikan, tapi model tetap harus bekerja keras karena ada noise.

```latex
\text{logit}(p) = \beta_0 + \beta_1 \log(\text{nominal dengan entitas Bank}) + \beta_2 \cdot \text{porsi tetangga nasabah Bank} + \beta_3 \cdot \text{tetangga baru bergabung} + \beta_4 \cdot \text{lama relasi} + \beta_5 \cdot \text{skala} + \beta_6 \cdot \text{sektor} + \varepsilon
```

| Sinyal | Jenis | Arah | Makna bisnis |
| --- | --- | --- | --- |
| Nominal transfer dengan entitas Bank | Graph | Positif, kuat | Semakin besar uang yang mengalir dari ekosistem Bank, semakin menarik pindah bank |
| Porsi tetangga yang nasabah Bank | Graph | Positif | Efek jaringan: mitra bisnisnya sudah di Bank |
| Tetangga baru bergabung bulan lalu | Graph, temporal | Positif | Efek menular dalam satu rantai pasok |
| Lama dan stabilitas relasi | Graph | Positif | Relasi yang rutin lebih mudah dikonversi |
| Sebagian besar relasi dengan bank lain | Graph | Negatif | Terikat kuat ke bank lain |
| Skala usaha | Tabel | Positif, lemah | Usaha menengah lebih butuh layanan bank |
| Sektor | Tabel | Campuran, lemah | Beberapa sektor lebih aktif bertransaksi |
| Noise acak |  |  | Supaya model tidak sempurna |

**Aturan label**

- Dua jendela walk-forward: validasi (fitur bulan 1-5, label bulan 6-11) dan test (fitur bulan 1-11, label bulan 12-17). Base rate 4% per jendela di antara kandidat yang belum jadi nasabah. Tidak ada data masa depan yang bocor ke fitur.
- Hasil run penuh: jendela 1 ada 1.798 yang jadi nasabah (460 perusahaan, 1.338 orang), jendela 2 ada 1.726 (574 perusahaan, 1.152 orang).
- Target porsi sinyal: sekitar 60% sampai 70% kekuatan prediksi dari sinyal graph. Cek dengan model sederhana setelah data dibuat.

**Mencegah data snooping:** simpan koefisien dan seed di file konfigurasi generator. Anggota yang melatih model tidak melihat koefisiennya sampai evaluasi selesai, supaya fitur tidak dirancang untuk "menebak rumus".

## 7. Data nasabah dan kepemilikan produk (pengganti Santander)

Data nasabah menggantikan data Santander untuk mesin NBO. Level dan pengaruh umur/penghasilan dari sumber Indonesia bila ada; laju buka-tutup bulanan masih dirujuk dari Santander karena belum ada data Indonesia. Tidak ada data orang sungguhan yang dipakai.

**Langkah pembuatan**

1. Bangkitkan penduduk 15-79 tahun (4x jumlah nasabah) dengan umur, jenis kelamin, provinsi, desa/kota, pekerjaan, dan pendapatan (bagian 5).
2. Tentukan siapa yang punya rekening bank dengan model inklusi SNLIK; nasabah Bank dipilih dari mereka.
3. Rekening utama mengikuti aturan katalog: di bawah 17 tahun Tabungan Plus Anak; mahasiswa, first jobber, dan anak muda 17-35 tahun Tabungan Plus Muda; lainnya Tabungan Plus.
4. Produk lain di bulan 1: peluang = level target x pengaruh umur x pengaruh pendapatan (KSEI untuk reksa dana dan obligasi; gradien penghasilan ASUMSI untuk deposito, giro, Prioritas, kartu kredit; Santander untuk sisanya), nol jika tidak layak menurut katalog; korelasi antar produk dijaga dengan Gaussian copula dari korelasi Santander.
5. Setiap bulan: pemegang menutup produk dengan laju nyata Santander; non-pemegang membuka dengan laju yang menjaga level tetap stabil; umur bertambah sehingga rekening utama ikut berganti; nasabah masuk dan keluar dengan laju median Santander.

**Aturan konsistensi dengan value chain**

- Nasabah yang pernah memegang Bank Payroll bekerja di perusahaan dengan bank\_payroll Bank.
- Nasabah Bank yang bekerja di perusahaan payroll Bank memegang Bank Payroll.
- Prospek perorangan bekerja di perusahaan yang menggaji lewat Bank, tetapi gajinya masuk ke rekening bank lain. Hanya dengan cara ini bank benar-benar melihat mereka (nama, bank penerima, nominal) di transfer gaji.
- person\_id yang sama dipakai di nasabah.csv, nasabah\_bulanan.parquet, persons.csv, employment.csv, dan transfers\_monthly.csv.
- Pedagang perorangan (6.478 orang, berwiraswasta, berbank lain) membeli dari distributor atau anchor nasabah Bank. Pembelian bulanan = penghasilan x 2 sampai 6 (ASUMSI), median sekitar Rp5,2 juta. Bank melihat mereka dari pembayaran yang masuk ke rekening Bank penjual; produk pembukanya Tabungan Plus Bisnis.

**Hubungan antarvariabel (supaya polanya masuk akal untuk Indonesia)**

| Hubungan | Aturan di generator | Sumber |
| --- | --- | --- |
| Gaji pegawai menurut umur | Log-normal per provinsi x jenis kelamin, dikali profil umur. Rata-rata nasional naik dari Rp2,0 juta (15-19 tahun) ke Rp3,9 juta (50-54), lalu turun ke Rp2,5 juta (60+). Puncak laki-laki di 50-54, perempuan di 55-59. Rata-rata provinsi tetap sama dengan BPS | BPS Keadaan Pekerja Agustus 2025, Tabel 4.41, 4.44, 4.45 (reference/bps\_upah\_umur\_2025.csv) |
| Penghasilan non-pegawai | Kelompok pendapatan SNLIK dikurangi porsi pegawai; tanpa profil umur karena BPS hanya mengukur buruh | SNLIK 2025, BPS Agustus 2025 |
| Punya rekening bank menurut penghasilan | Naik dari 65,6% (di bawah Rp500 ribu) ke 97,6% (di atas Rp3,5 juta), sebelum diskalakan ke sektor perbankan | SNLIK 2025 Lampiran 18 dan 20 |
| Reksa dana dan obligasi menurut umur dan penghasilan | Pemegang mengikuti sebaran investor: 54% berumur 30 tahun ke bawah, 48% berpenghasilan Rp10-100 juta per tahun | KSEI Statistik Publik Oktober 2025 (reference/ksei\_investor\_2025.csv) |
| Deposito, giro, Prioritas, kartu kredit menurut penghasilan | Peluang sebanding dengan (penghasilan / median) pangkat beta: deposito 0,7; giro 0,5; Prioritas 1,5; kartu kredit 0,5. Kartu kredit tetap hanya untuk 21+ dan minimal Rp3 juta | ASUMSI di config.yaml (produk.gradien\_pendapatan); belum ada data publik Indonesia per penghasilan |

Batasan yang diketahui: kartu kredit dimiliki 74% nasabah di kuintil penghasilan teratas. Ini karena jumlah kartu AKKI dibagi dengan asumsi 1 kartu per pemegang. Jika tim menemukan jumlah pemegang kartu, ubah produk.kartu\_per\_pemegang di config.

**Peran Santander sekarang kecil:** Santander adalah data ritel Spanyol 2015-2016, tanpa segmen korporasi, jauh lebih sempit dari Bank yang melayani perorangan, UMKM, dan wholesale. Generator hanya memakainya untuk dua hal yang belum ada data Indonesianya: laju buka-tutup produk per bulan dan produk yang dipegang bersamaan. Kemiripan dengan Santander dilaporkan sebagai INFO, tidak menentukan lolos atau gagal. Pengaruh umur dan penghasilan memakai BPS, SNLIK, dan KSEI; data wholesale memakai katalog Bank, aturan BI, dan interview.

## 8. Aturan realisme, waktu, PII, dan fairness

Data sintetis hanya berguna kalau tidak bocor, tidak bias, dan masuk akal bagi orang bank. Aturan berikut wajib diikuti generator.

| Aspek | Aturan |
| --- | --- |
| Lookahead bias | Atribut dan relasi di bulan t hanya boleh bergantung pada bulan sebelum t. Status nasabah berubah hanya pada tanggal\_jadi\_nasabah. |
| Survivorship bias | Perusahaan dan orang boleh muncul dan hilang di tengah periode (berdiri, tutup, pindah kerja). Jangan hanya membuat entitas yang hidup sepanjang 17 bulan. |
| Konsistensi bisnis | Omzet, jumlah karyawan, dan nominal transfer sesuai skala; total gaji perusahaan tidak melebihi omzet; anchor selalu nasabah Bank. |
| PII | Tidak ada nama asli, NIK, nomor rekening, alamat, atau nomor telepon. ID memakai pola buatan (C000123, P0045678). Nama bank lain disamarkan. |
| Fairness | Jenis kelamin dan usia dibangkitkan tanpa memengaruhi peluang akuisisi secara langsung, supaya audit fairness punya baseline yang adil. Bias yang sengaja ditanam untuk uji harus dicatat. |
| Reproducibility | Satu seed tetap, satu file konfigurasi parameter, generator bisa dijalankan ulang dan menghasilkan data yang sama persis. |
| Transparansi | Setiap angka asumsi (base rate, porsi sinyal, distribusi provinsi) ditulis di konfigurasi beserta sumber atau alasannya. |

## 9. Validasi otomatis

Setiap run menulis validation\_report.md dengan 52 cek LOLOS/GAGAL dan 4 baris INFO. Cek mencakup 3 cek kepatuhan (syarat produk saat dibuka, kartu kredit sesuai BI PADG 32/2025, nasabah di bawah 17 tahun hanya memegang rekening anak), 4 cek realisme data bank (bagian 12), 1 cek data kotor (bagian 13), 6 cek hubungan antarvariabel (gaji menurut umur, produk menurut penghasilan), 12 cek data wholesale termasuk label per jendela dan KUR (bagian 14), dan 1 cek pedagang. Run penuh terakhir (seed 42, 9 Okt 2026): 52 dari 52 LOLOS. Baris INFO membandingkan churn, pola kepemilikan bersama, dan arus nasabah dengan Santander tanpa menentukan lolos/gagal, karena Santander adalah data ritel Spanyol 2015-2016 yang jauh lebih sempit dari segmen Bank. Data boleh dipakai tim model hanya jika semua cek lolos; hasil cek juga menjadi bahan slide EDA (rubrik Hari 2).

| Kelompok cek | Dibandingkan dengan | Hasil run penuh |
| --- | --- | --- |
| Sebaran umur, gender, pekerjaan, pendapatan, desa/kota | SNLIK 2025 | Selisih maksimal di bawah 2 poin persen |
| Upah pegawai per kelompok dan per provinsi | BPS Agustus 2025 | Median rasio rata-rata provinsi sekitar 0,99; kelompok upah meleset maksimal sekitar 6 poin (log-normal) |
| Profil upah menurut umur, per jenis kelamin | BPS Agustus 2025, Tabel 4.41, 4.44, 4.45 | Rasio upah per kelompok umur meleset maksimal 10,9% dari rasio BPS |
| Inklusi perbankan per umur, pekerjaan, pendapatan | SNLIK 2025 | Total 70,5% vs 70,65% |
| Level 12 produk tambahan | Target per sumber | Dalam 3 standard error |
| Pemegang reksa dana dan obligasi per umur dan per penghasilan tahunan | KSEI Statistik Publik Oktober 2025 | Selisih maksimal 4,2 poin persen |
| Kepemilikan deposito, giro, Prioritas, kartu kredit per kuintil penghasilan | Arah: naik dengan penghasilan (gradien ASUMSI di config) | Q5 lebih tinggi dari Q1 untuk semua; Prioritas 18,2% vs 0,6%, deposito 10,6% vs 1,9% |
| Laju tutup produk per bulan | Santander | INFO saja: dalam batas noise Poisson |
| Pola kepemilikan bersama | Korelasi Santander | INFO saja: 0,48, karena produk yang bentuknya dari data Indonesia ikut naik bersama penghasilan |
| Arus nasabah masuk dan keluar | Median Santander | INFO saja: 0,72% dan 0,18% per bulan |
| Degree anchor, nominal per skala, skewness, porsi UNKNOWN | Guideline bagian 5 | Long tail, naik sesuai skala, miring ke kanan, sekitar 31% |
| Lonjakan payroll bulan THR | Aturan THR 1x upah | 2,00x bulan biasa |
| Konsistensi payroll, ID unik, pihak transfer, tidak ada kartu kredit di bawah 17 tahun | Aturan guideline dan katalog | 0 pelanggaran |
| Base rate dan kekuatan sinyal graph | Guideline bagian 6 | 4,0% per jendela; AUC graph 0,71 vs tabel (sektor) 0,56, memakai fitur yang terlihat bank saja; tidak melebihi 0,95 |
| Data wholesale: channel, fasilitas, tanggal produk, katalog, debitur per RM, kontak, label | Batas BI, katalog Bank, interview (bagian 14) | 0 pelanggaran; 36,9 debitur dan 18,1 non-debitur per RM; minimal 111 label per jendela; AUC label sekitar 0,73 di jendela test |

Siapa yang membaca laporan: sebaiknya bukan orang yang menjalankan generator, supaya ada pemeriksaan kedua.

## 10. Format output dan serah terima

Generator berdiri sendiri di folder synthetic\_generator dan bisa disalin utuh ke project baru.

```
pip install -r requirements.txt
python run.py                  # ukuran penuh, sekitar 1 menit
python run.py --nasabah 5000   # cepat untuk mencoba
```

| Isi folder | Fungsi |
| --- | --- |
| run.py | Menjalankan semua tahap dan validasi |
| config.yaml | Semua ASUMSI tim dan koefisien label (jangan dibuka pembuat model sampai evaluasi) |
| reference/ | Data resmi BPS, OJK, AKKI, LPS, katalog Bank, hasil kalibrasi Santander, dan SUMBER.md |
| calibrate/ | Skrip pengukur pola perilaku dari data Santander asli (opsional dijalankan ulang) |
| generator/ | Kode: people, products, customers, value\_chain, acquisition, wholesale, export, dirty, validate |
| output/ | data\_bank/ (yang terlihat bank, dipakai tim), kunci\_evaluasi/ (kebenaran lengkap, hanya evaluasi), validation\_report.md; tidak di-commit, bisa dibuat ulang dengan seed yang sama |

**Kebutuhan PRD yang sudah dipenuhi data**

| Kebutuhan PRD | Dipenuhi oleh |
| --- | --- |
| Mesin NBO dan walk-forward 17 bulan | nasabah\_bulanan.parquet |
| Dashboard ekosistem: porsi dana ke bank lain per anchor | transfers\_monthly.csv + bank\_utama di companies.csv dan persons.csv |
| Klaster dan entitas berpengaruh | Relasi anchor-mitra-sub-supplier di transfers dan relationship\_truth |
| Daftar prospek perusahaan dan perorangan | acquisitions.csv (kolom tipe) |
| Baseline akuisisi "nominal transfer terbesar" | total\_nominal\_rp per bulan |
| Produk pembuka | produk\_pertama dari katalog Bank |
| Demo guardrail nasabah 16 tahun | Nasabah 15-16 tahun ada di nasabah.csv (rekening utama Tabungan Plus Anak) |
| Audit fairness | jenis\_kelamin, umur, provinsi di nasabah.csv |

Catatan: anchor showcase untuk cerita demo belum dipilih otomatis. Pilih dari companies.csv anchor dengan relasi terbanyak dan porsi dana ke bank lain terbesar.

## 11. Pertanyaan terbuka untuk tim

Generator sudah berjalan; keputusan berikut masih terbuka untuk tim.

- [ ] Apakah asumsi di config.yaml (porsi perusahaan Bank, skala mitra, koefisien label) sudah disetujui tim dan bisa dipertahankan di depan penguji?
- [ ] Anchor mana yang dipakai sebagai cerita utama demo?
- [ ] Saldo dan transaksi sudah ada untuk nasabah korporasi (bagian 14); perlu juga untuk nasabah perorangan?
- [ ] Produk yang belum disimulasikan (Tabungan Berencana, Simpanan Pelajar, produk syariah) perlu ditambah?
- [ ] Siapa yang membaca validation\_report.md sebagai pemeriksa kedua?
- [ ] Ukuran data: 50 ribu nasabah cukup, atau perlu diperbesar untuk model?

## 12. Data yang realistis dilihat bank

Data sintetis hanya berguna jika setiap kolom yang dipakai model memang dimiliki bank di dunia nyata dan boleh dipakai. Karena itu output dibagi dua: data\_bank/ berisi hanya yang terlihat bank, kunci\_evaluasi/ berisi kebenaran lengkap untuk membangkitkan data dan menilai model. Status setiap kolom ada di kamus\_data.csv.

| Status | Arti | Contoh |
| --- | --- | --- |
| HIJAU | Ada di sistem bank dan boleh dipakai | Kepemilikan produk, data KYC nasabah (umur, provinsi, pekerjaan, kisaran pendapatan), channel |
| KUNING | Ada di bank, pemakaian dibatasi | Transfer ke rekening bank lain, penerima gaji dari rekening Bank, pemilik perusahaan nasabah (hanya analisis internal; lihat PRD bagian 18) |
| ORANYE | Tidak ada di bank, bisa dicari dari sumber sah | Sektor, provinsi, tahun berdiri perusahaan prospek (OSS/NIB, AHU); jenis relasi ditebak dari pola transfer |
| MERAH | Tidak akan dimiliki bank | Demografi dan pendapatan prospek perorangan, omzet dan karyawan perusahaan prospek, transfer antar dua pihak non-nasabah, pendapatan pasti nasabah, relationship\_truth |

**Aturan di data\_bank/**

- Transfer hanya yang salah satu sisinya nasabah Bank; transfer antar dua pihak non-nasabah tidak terlihat.
- Orang dan perusahaan non-nasabah hanya muncul jika terlihat di transfer tersebut; kolom MERAH dikosongkan.
- Pendapatan nasabah hanya berupa kisaran (seperti formulir KYC), bukan angka pasti.
- Kandidat akuisisi hanya yang terlihat bank (32.720 dari 44.955 di run penuh).

**Aturan untuk model:** fitur hanya dari kolom yang boleh\_fitur\_model = ya di kamus\_data.csv. Label akuisisi tetap mengikuti kondisi sebenarnya, karena di dunia nyata keputusan pindah bank juga dipengaruhi hal yang tidak terlihat bank. Dengan fitur yang realistis, sinyal graph menghasilkan AUC 0,71 (tabel saja 0,56); lebih rendah dari versi yang memakai data tersembunyi, tetapi jujur.

Pemetaan sumber nyata berdasarkan praktik umum perbankan dan regulasi (KYC/APU-PPT, sistem transfer BI-FAST/SKN/RTGS); detail di Bank perlu dikonfirmasi ke tim data atau IT Bank.

## 13. Data kotor terkontrol untuk EDA

Data sintetis yang terlalu bersih tidak memberi apa pun untuk dinilai di rubrik Data Preparation & EDA (Hari 2, 7,5%). Karena itu data\_bank/ sengaja berisi masalah kualitas data yang biasa ada di ekstrak bank, sedangkan kunci\_evaluasi/ tetap bersih sebagai kunci jawaban. Run penuh menanam 122.451 perubahan, semuanya tercatat di kunci\_evaluasi/catatan\_data\_kotor.csv (file, kolom, jenis, id, nilai asli, nilai kotor).

| Jenis masalah | Di mana | Porsi (config, ASUMSI) | Contoh |
| --- | --- | --- | --- |
| Nilai hilang | nasabah: kisaran pendapatan, pekerjaan, provinsi, channel; bulanan: flag kartu kredit, flag mobile banking, segmen; transfer: jumlah transaksi; perusahaan: tahun berdiri | 0,2% sampai 5% per kolom | kisaran\_pendapatan kosong |
| Variasi teks | provinsi, jenis kelamin, pekerjaan, sektor, nama perusahaan | 2% sampai 3% per kolom | JAWA TENGAH, jawa timur, ' Sulawesi Selatan', 'Laki-Laki ', singkatan L/P/Jakarta/Jogja |
| Outlier | usia; nominal transfer | 0,1% sampai 0,3% | usia -1, 0, 150, 999; nominal x1000 atau negatif |
| Duplikat baris | nasabah, data bulanan, transfer, transaksi counterparty, lead Bisdev | 0,2% sampai 1% | Baris yang sama muncul dua kali |

**Aturan**

- Porsi diatur di config.yaml bagian data\_kotor; aktif: false menghasilkan data\_bank/ bersih.
- Masalah hanya ditanam di data\_bank/; kunci\_evaluasi/ tidak pernah disentuh.
- Setiap variasi teks dijamin berbeda dari nilai asli, sehingga catatan kunci jawaban akurat.
- Validasi mengecek jumlah yang ditanam sama dengan porsi config dan semuanya tercatat.

**Cara tim memakai:** bersihkan data\_bank/ di notebook EDA (imputasi, standardisasi teks, aturan rentang usia dan nominal, deduplikasi), lalu bandingkan hasilnya dengan kunci\_evaluasi/ untuk menunjukkan akurasi pembersihan di slide Hari 2.

## 14. Data wholesale dari interview RM dan PS

Interview RM Transactional segmen commercial dan Product Specialist (Oktober 2026) menambah 7 tabel perusahaan untuk fitur F19 sampai F22 di PRD. Perusahaan, relasi anchor, dan transfer yang sudah ada dipakai ulang; tabel baru menambah lapisan yang dilihat RM wholesale. Status: sudah dibuat di generator/wholesale.py dan lolos semua cek pada run penuh 9 Oktober 2026.

**Tabel baru**

| Tabel | Kolom utama | Ukuran default | Aturan dan sumber |
| --- | --- | --- | --- |
| rm\_portofolio.csv | rm\_id, cabang, company\_id, status\_debitur, segmen | 23 RM (19 Commercial, 4 Corporate) dari 1.233 nasabah; rata-rata 36,9 debitur dan 18,1 non-debitur per RM (target interview 40 dan 15) | Angka per RM dari interview (perlu validasi); jumlah RM = ASUMSI ukuran |
| companies.csv (kolom tambahan) | cif (hanya nasabah Bank), segmen, status\_debitur, rm\_id, cabang | 20.050 perusahaan; 5.099 nasabah Bank (UMKM 2.689, RCC 1.177, Commercial 1.026, Corporate 207) | Segmen dari omzet: RCC di bawah Rp10 miliar, Commercial Rp10-150 miliar (interview, belum final), Corporate di atasnya (ASUMSI) |
| transaksi\_counterparty\_bulanan.csv | bulan, company\_id, counterparty\_nama, counterparty\_bank, arah (masuk/keluar), channel, jumlah\_transaksi, total\_nominal\_rp, kelas\_nama\_bank | Sekitar 570 ribu baris | Channel mengikuti batas Bank Indonesia: BI-FAST sampai Rp250 juta, SKN sampai Rp1 miliar, RTGS di atas Rp100 juta; sesama Bank = pemindahbukuan. Pilihan channel di rentang yang tumpang tindih = ASUMSI |
| saldo\_bulanan.csv | company\_id, bulan, saldo\_akhir\_bulan\_rp, saldo\_rata2\_rp | 17 bulan x nasabah Bank | Saldo akhir bulan dipakai RM untuk target ending balance (interview); hubungan saldo dengan arus masuk-keluar = ASUMSI |
| riwayat\_produk\_wholesale.csv | company\_id, produk, no\_katalog, tanggal\_mulai, tanggal\_selesai, status, beneficiary\_id, nilai\_proyek\_rp, konteks | 1-6 produk per nasabah Bank; nasabah UMKM memakai QRIS Bank (207) dan EDC Bank (199) | Nama dan nomor dari katalog Bank (lihat tabel kebutuhan ke produk); beneficiary bisa anchor atau instansi pemberi proyek |
| fasilitas\_pembiayaan.csv | company\_id, produk, plafon\_rp, baki\_debet\_rp, tanggal\_mulai, jatuh\_tempo | Hanya debitur | Kredit Modal Kerja (no. 112), Kredit Investasi (113), Supply Chain Financing (161); plafon naik dengan omzet (ASUMSI). UMKM memakai KUR Mikro (108) sampai Rp100 juta dan KUR Kecil (109) sampai Rp500 juta (batas Mikro = ASUMSI) |
| lead\_bisdev.csv | lead\_id, nama\_perusahaan, anchor\_terkait, sektor, kota, tanggal\_update | Sekitar 1.500 lead | Meniru file Excel Bisdev: sering hanya nama, kolom lain banyak kosong, diperbarui beberapa hari sekali, lebih banyak counterpart bernilai besar |

Kontak atau PIC tidak dibuat untuk perusahaan non-nasabah. Untuk nasabah ber-CIF hanya ada flag ada\_pic\_terdaftar, tanpa nama atau nomor.

**Klasifikasi nama x bank.** Setiap baris transaksi diberi satu dari 4 kelas, sesuai data yang pernah diterima RM:

| Kelas | Arti | Sinyal untuk RM |
| --- | --- | --- |
| Nama sama, bank sama | Pemindahan antar-rekening sendiri di Bank | Normal |
| Nama sama, bank beda | Dana nasabah dipindah ke rekening sendiri di bank lain | Retensi atau win-back: cek rate, pembiayaan di bank lain |
| Nama beda, bank sama | Bayar atau terima dari nasabah Bank lain | Closed loop sudah terjadi; peluang tambah produk |
| Nama beda, bank beda | Counterpart di bank lain | Prospek akuisisi (NTB) |

**Sinyal yang ditanam** (untuk F19): counterpart baru (muncul pertama kali), counterpart berulang (muncul 3 bulan atau lebih), transaksi besar (5% teratas per perusahaan), dan perpindahan bank (porsi nama sama/bank beda naik dari bulan ke bulan). Porsi tiap sinyal = ASUMSI di config.

**Kebutuhan ke produk** (untuk F20 dan pembangkitan riwayat produk)

| Kebutuhan bisnis | Produk katalog Bank (no.) | Pemicu di data |
| --- | --- | --- |
| Penempatan dana | Bank Giro Non Perorangan (162), Deposito Non Perorangan (163) | Saldo rata-rata tinggi |
| Operasional dan penagihan | Virtual Account (141, 157), CIB (165), CIB Cash (166) | Banyak transaksi masuk dari banyak pihak |
| Trade | Ekspor L/C (121), Impor L/C (122), SKBDN (123), SBLC (124), Garansi Bank (160) | Sektor perdagangan dan industri; proyek dengan beneficiary |
| Rantai pasok | Supply Chain Financing (161), CIB Supply Chain (170) | Relasi supplier atau distributor ke anchor |
| Pembiayaan | Kredit Modal Kerja (112), Kredit Investasi (113) | Status debitur, arus kas, omzet |
| Likuiditas grup | Cash Pooling (151), Account Sweep (150) | Beberapa rekening atau entitas satu grup |
| Karyawan | Payroll Korporasi (120), lalu Fleksi (37) dan KPR (30) untuk karyawan | Jumlah karyawan; menyambung ke data perorangan |

Pemetaan ini dari contoh di interview (bagian 11.3) dan harus dicek RM dan PS. Jumlah produk per perusahaan naik dengan omzet, tetapi perusahaan kecil tetap bisa memakai banyak produk (interview bagian 11.4); kekuatan hubungannya = ASUMSI. SKB dan DLN dari catatan interview belum dipakai: di katalog hanya ada SKBDN, dan DLN tidak ditemukan.

**Label baru (data\_bank/label\_wholesale.csv, seperti acquisitions.csv; bukan fitur)**

- konversi\_ntb: counterpart non-nasabah membuka rekening dalam 6 bulan (memperluas label akuisisi bagian 6)
- non\_debitur\_ke\_debitur: non-debitur mendapat fasilitas dalam 6 bulan
- cross\_sell\_wholesale: nasabah menambah produk wholesale dalam 6 bulan
- reaktivasi: produk yang pernah berhenti aktif lagi dalam 6 bulan
- leakage: porsi transaksi keluar ke bank lain naik dan bertahan 3 bulan

Semua label dibuat dari rumus yang diketahui seperti bagian 6, dengan koefisien disembunyikan sampai evaluasi. Base rate per jendela 6 bulan: non-debitur ke debitur 8% (proksi kredit investasi nasional +17,98% dan kredit korporasi Bank +10,4% per tahun; UMKM mendapat KUR), cross-sell 11% (proksi pengguna CIB +24,8% per tahun), reaktivasi 15% dan leakage 5% (ASUMSI). Label ada di dua jendela, validasi (bulan 6-11) dan test (bulan 12-17), dengan minimal 100 label per jendela.

| Label | Jendela 1 (bulan 6-11) | Jendela 2 (bulan 12-17) |
| --- | --- | --- |
| non\_debitur\_ke\_debitur | 255 | 235 |
| cross\_sell\_wholesale | 569 | 543 |
| reaktivasi | 131 | 111 |
| leakage | 121 | 116 |

Corporate hanya 207 nasabah, sesuai proporsi dunia nyata. Saat melatih model, kelas atau segmen yang sedikit boleh di-oversample di data train saja; data validasi dan test tetap asli.

**Pembagian data\_bank/ dan kunci\_evaluasi/**

- Terlihat bank: transaksi yang punya sisi Bank, termasuk nama dan bank lawan transaksi; saldo, produk, dan fasilitas nasabah Bank.
- Kosong untuk non-nasabah: omzet, jumlah karyawan, kontak, dan produk di bank lain.
- Hanya di kunci\_evaluasi/: relasi lengkap anchor-mitra, pasangan lead ke company\_id (lead\_bisdev\_kunci.csv), counterpart yang pindah bank (counterparty\_pindah\_bank.csv), dan flag rekening sendiri di bank lain.

**Data kotor tambahan (bagian 13)**

- counterparty\_nama dan nama\_perusahaan di lead\_bisdev ditulis dengan variasi: "PT. Maju Jaya", "MAJU JAYA PT", "PT Maju Jaya Tbk". Tugas EDA-nya adalah entity resolution.
- lead\_bisdev: anchor\_terkait kosong 31%, sektor 69%, provinsi 70% (ASUMSI dari "sering hanya nama"), 40% nama ditulis beragam, dan 3% lead terkirim dua kali.
- saldo\_bulanan: 1% saldo akhir bulan hilang dan 0,1% saldo rata-rata salah ketik (x1000 atau negatif).

**Cek validasi data wholesale**

- 0 transaksi BI-FAST di atas Rp250 juta, 0 SKN di atas Rp1 miliar, 0 RTGS sampai Rp100 juta
- Setiap transaksi di data\_bank punya sisi Bank
- Fasilitas pembiayaan hanya untuk debitur; tanggal produk konsisten (mulai sebelum selesai, di dalam panel)
- Jumlah debitur dan non-debitur per RM sesuai config
- Kontak hanya ada untuk perusahaan ber-CIF
- Base rate setiap label sesuai config; label tidak terlalu mudah (AUC di bawah 0,95)

**Field output lead dari interview ke kolom data**

| Field output (interview bagian 14) | Kolom sumber |
| --- | --- |
| Anchor, counterparty, relationship | relations, transaksi\_counterparty\_bulanan |
| Status Bank | cif ada atau tidak; kelas\_nama\_bank |
| Sinyal transaksi | jumlah\_transaksi, total\_nominal\_rp, bulan pertama dan terakhir muncul |
| Produk existing, riwayat, status, beneficiary, nilai proyek | riwayat\_produk\_wholesale |
| Produk potensial dan alasan | Skor model + tabel kebutuhan ke produk |
| Kontak/PIC | Hanya flag ada\_pic\_terdaftar untuk ber-CIF |
| Prioritas, next best action | Output model + aturan F21 |

**Sumber yang dicek:** [detikFinance, "BI Fast Adalah: Kenali Manfaat serta Bedanya dengan RTO, RTGS, dan SKNBI"](https://finance.detik.com/moneter/d-6817089/bi-fast-adalah-kenali-manfaat-serta-bedanya-dengan-rto-rtgs-dan-sknbi) untuk batas BI-FAST Rp250 juta, SKNBI Rp1 miliar, dan RTGS di atas Rp100 juta per transaksi (FAQ BI-FAST resmi di bi.go.id menolak diunduh saat dicek); katalog produk\_bank\_knowledge.csv untuk nama dan nomor produk; catatan gabungan interview RM dan PS.
