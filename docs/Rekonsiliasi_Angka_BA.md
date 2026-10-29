# Rekonsiliasi Angka: Business Case BA vs Sistem RM Copilot

Disusun 11 Oktober 2026 untuk diskusi tim (BA, Data Scientist, AI Engineer) sebelum demo 15 Oktober.
Dokumen BA di `docs/Business/` **tidak diubah**; dokumen ini hanya mencatat perbandingan, alasan, dan usulan.

Sumber yang dibandingkan:

| Pihak | File |
|---|---|
| BA | `docs/Business/Assumptions.csv`, `Model.csv`, `Bridge.csv`, `Issue.csv`, `Ratio_check.csv`, `Summary.csv` |
| Sistem | `docs/asumsi_f12.csv` (dipakai halaman Profit), `src/impact/profit.py`, `docs/Hasil_Model.md`, `docs/Hasil_DeepEval.md`, `outputs/model/ringkasan_model.csv` |

Semua angka sistem berasal dari **data sintetis**. Angka BA sebagian besar berasal dari business case awal dan ditandai sendiri oleh BA sebagai *unverified* atau *placeholder*.

## 1. Ringkasan

- Kerangka analisis BA lebih kuat dari halaman Profit di sistem dan sebaiknya dipakai untuk pandangan program: lift realization, faktor pendapatan tahun pertama, biaya risiko kredit, biaya proyek yang terlewat, dan larangan menghitung ganda.
- Sebagian input BA (tingkat konversi) masih dari business case. Sistem sekarang punya angka terukur yang bisa menggantikannya.
- Temuan terpenting: untuk prospek perusahaan, lift 4x yang dipakai BA memang muncul, tapi asalnya dari **data counterpart yang terlihat**, bukan dari model ML. Model hanya setara dengan aturan RM yang sudah ada.
- PDF BA memuat beberapa klaim yang sudah basi (AUC 0,91 "Validated", data Santander, guardrail OpenAI Moderation) dan format yang bisa terbaca sebagai dokumen resmi Bank.

## 2. Yang sudah tepat di analisis BA

| Temuan BA (`Issue.csv`) | Kenapa penting |
|---|---|
| #1 Kenaikan pendapatan dan penghematan kontak tidak bisa terjadi bersamaan | Menghapus Rp33 M dari klaim awal yang tidak mungkin |
| #2 Jam RM bukan uang tunai | Menghapus Rp41,6 M nilai kapasitas yang dihitung ganda |
| #3 Lift ranking bukan lift kausal | Butuh grup kontrol; sementara pakai lift realization 40/60/80% |
| #5–6 Pendapatan bukan profit; limit tidak terpakai penuh sepanjang tahun | Menambahkan biaya risiko, opex, drawn share, dan faktor tahun pertama 50% |
| #8 Investasi tidak lengkap | Menambah biaya tim, change management, dan kepatuhan |
| #13 Outreach massal sudah untung di biaya per kontak business case | Model sebaiknya dipakai untuk meranking ulang di kapasitas yang sama, bukan memangkas kontak |

Hasil BA (Base): tahun 1 bersih −Rp9,05 M, 3 tahun kumulatif +Rp131,14 M, payback 14 bulan. Pesan akhir BA "positif tapi tidak luar biasa, label sebagai simulasi" sejalan dengan temuan sistem.

## 3. Perbandingan angka

### 3.1 Tingkat konversi (paling penting)

BA memakai angka business case tanpa sumber. Sistem mengukur angka yang setara di jendela test (presisi pada 10% teratas; NBO pada 1% teratas).

| Segmen | BA: tanpa model → dengan model | Sistem: acak / aturan RM / model | Model vs aturan RM |
|---|---|---|---|
| Wholesale value chain (prospek perusahaan) | 3% → 12% (4,0x) | 4,1% / 11,9% / 12,0% | **1,01x** |
| Payroll (karyawan) | 2,5% → 7,5% (3,0x) | 7,8% / 9,1% / 23,8% | 2,61x |
| Pedagang (program anchor) | tidak ada | 4,9% / 4,9% / 22,7% | 4,67x |
| Cross-sell wholesale | tidak ada | 10,6% / 36,9% / 43,5% | 1,18x |
| Ritel digital / NBO | 0,8% → 2,4% (3,0x) | 0,2% / 0,4% / 7,5% (top 1%) | 19,4x |

Alasan dan dampak:

1. **Prospek perusahaan.** Angka BA (3% → 12%) ternyata hampir sama dengan angka sistem (acak 4,1% → model 12,0%). Tapi pembanding yang tepat adalah cara kerja RM sekarang, yaitu mengurutkan prospek dari nominal transaksi, yang sudah mencapai 11,9%. Uji bootstrap mengonfirmasi model tidak signifikan lebih baik dari aturan itu (+0,011 ROC-AUC, CI 95% [−0,001; 0,023]). Jadi nilai 4x berasal dari **melihat counterpart nasabah di data transaksi** (fitur F19 dan graph), bukan dari ranking ML. Untuk business case, lift wholesale sebaiknya dikreditkan ke data dan alur kerja, dengan model sebagai pelengkap.
2. **Payroll.** Rasio BA (3x) konsisten dengan sistem (3,0x vs acak). Sistem menambahkan bahwa model juga 2,6x lebih baik dari aturan sederhana.
3. **Ritel/NBO.** Tidak bisa dibandingkan langsung karena potongannya berbeda (BA: populasi target mobile banking; sistem: 1% teratas pasangan nasabah-produk). Arah temuannya sama: model jauh lebih baik dari produk terpopuler.
4. **Catatan skala.** Semua angka sistem adalah hasil simulasi; lift realization BA (40/60/80%) tetap perlu dipakai karena lift ranking bukan lift kausal.

### 3.2 Nilai dan biaya per unit

| Parameter | BA | Sistem (`asumsi_f12.csv`) | Usulan | Alasan |
|---|---|---|---|---|
| Biaya kunjungan RM | Rp200 rb (business case, *unverified*) | Rp750 rb (ASUMSI) | **Rp750 rb**, divalidasi ke RM | Dengan tarif BA sendiri Rp370 rb per jam produktif, kunjungan 2–3 jam termasuk perjalanan sudah ≥Rp750 rb |
| Biaya kontak ritel | Rp15 rb (sel tertulis 0,02 jt) | Rp15 rb | Rp15 rb | Sama; sel BA perlu dirapikan agar tidak terbaca Rp20 rb |
| Spread kredit wholesale | 2,5% bersih; risiko 0,7% dan opex 0,25% (Base) | 4,5% (NII Rp40,33 T / kredit Rp899,53 T) dikurangi EL 1,5% | **Pakai angka BA untuk wholesale** | Yield kredit korporasi lebih tipis dari rata-rata bank; 4,5% adalah proksi seluruh portofolio |
| Spread kredit ritel (Fleksi) | 6,0%; risiko 1,5%, opex 0,4%; saldo rata-rata 85% | 4,5% dikurangi EL 1,5% | Keduanya boleh | Hasil per pinjaman hampir sama |
| Nilai Fleksi per pinjaman per tahun | Rp1,74 jt (Base) | Rp1,8 jt | Selaras | Metode berbeda tapi saling menguatkan |
| Nilai fasilitas wholesale per tahun | Rp25,19 jt (Base, limit Rp2,5 M) | Sistem tidak memodelkan fasilitas kredit baru; akuisisi perusahaan dinilai dari saldo dana + fee CIB, cross-sell dari fee rata-rata Rp9 jt | Diskusikan | Definisi nilainya berbeda: BA berbasis kredit, sistem berbasis dana dan fee. BA sendiri menandai limit Rp2,5 M "large for an SME supplier" |
| Nilai mobile banking / ritel digital | ARPU Rp350 rb × 60% = Rp210 rb | Rp60 rb | **Belum diputuskan** | Definisinya berbeda: BA menghitung kartu dan wealth yang dijual lewat app, sistem hanya nilai app. Keduanya tanpa sumber |
| Waktu persiapan pitch | 3 jam → 0,75 jam (−75%); di PDF juga "15 → 2 menit" dan "−85%" | Agent menyusun paket dalam 15–27 detik (terukur) | Ukur dengan RM | Tiga angka berbeda di dokumen BA; waktu RM membaca dan memvalidasi paket belum diukur |
| Biaya salah jual yang dicegah | tidak ada | Rp2 jt per kasus yang diblokir guardrail | Tambahkan ke BA sebagai *upside* | Sumber nilai yang belum ada di business case |

### 3.3 Fakta makro

| Angka | BA | Status |
|---|---|---|
| Kredit Bank Rp899,53 T | (tersirat dari Rp518,2 T = 57,6%) | Konsisten dengan sumber sistem (Kontan, 3 Feb 2026) |
| Total aset Rp1.362,06 T, laba Rp20,04 T, NIM 3,8%, CIR 46,5% | Ditulis di PDF | Ditandai *unverified* di `Ratio_check.csv`; perlu tautan laporan keuangan Bank sebelum dipresentasikan |
| Klaim NIM +12–18 bps, densitas produk +0,4–0,6 | Sudah dikoreksi BA (≈1 bp dan +0,0014) | Ikuti koreksi BA; jangan pakai klaim awal |

## 4. Yang basi atau perlu diperbaiki di PDF BA

| Bagian PDF | Tertulis | Kondisi sekarang |
|---|---|---|
| Kartu ringkasan, Tabel 4 | 0,91 AUC, "Validated" | Itu angka PoC Santander. Sekarang (data sintetis): NBO 0,946; akuisisi 0,725; prospek perusahaan tidak signifikan vs baseline (`docs/Hasil_Model.md`) |
| Tabel 6, pertanyaan pertama | Model dilatih di data Santander | Sistem memakai data sintetis penuh yang dikalibrasi ke data resmi Indonesia; Santander hanya rujukan bentuk perilaku |
| Tabel 5 guardrail | OpenAI Moderation, 5 tool, maksimal 5 langkah | Gemma lokal + lapisan semantik, aturan regex, 6 tool hanya-baca, maksimal 6 langkah |
| Tabel 4 kode fitur | F17 = Assumptions Register, F18 = control pilot | Di PRD: F17 = RM Copilot Agent, F18 = Tanya AI |
| Bagian 5 | ~5.000 perusahaan, ~20.000 individu | 20.000 perusahaan, 50.000 nasabah awal, 50 anchor; graph 94.461 node dan 973.369 relasi |
| Kop dan penutup | "Bank", "Strictly Confidential – Board", "audited, board-ready", permintaan persetujuan capex Rp18,5 M | Bisa terbaca seperti dokumen resmi Bank. Usul: label jelas "Simulasi capstone, bukan dokumen resmi bank", sesuai rekomendasi BA sendiri di `Summary.csv` |
| Tabel 6, waktu riset | 15 → kurang dari 2 menit; −85% | Samakan dengan satu angka setelah diukur bersama RM |

## 5. Usulan keputusan tim

| # | Keputusan | Usulan | Pemilik |
|---|---|---|---|
| 1 | Sumber tingkat konversi di model BA | Ganti angka business case dengan angka terukur di bagian 3.1; pisahkan nilai dari data counterpart dan nilai dari model untuk wholesale | BA + DS |
| 2 | Biaya kunjungan RM | Rp750 rb, divalidasi ke RM saat demo dry-run | BA |
| 3 | Spread kredit | Wholesale pakai angka BA, ritel pakai angka sistem; satukan di `asumsi_f12.csv` | BA + DS |
| 4 | Nilai mobile banking | Sepakati definisi (app saja atau termasuk produk yang dijual lewat app) | BA |
| 5 | Satu daftar asumsi | `asumsi_f12.csv` dan `Assumptions.csv` sekarang terpisah dan angkanya beda; jadikan satu sumber untuk demo | BA + DS |
| 6 | PDF BA | Perbarui metrik model, guardrail, kode fitur, ukuran graph, dan label simulasi | BA |
| 7 | Cara menyajikan dua angka profit | Halaman Profit = hasil terukur di sampel simulasi (per kampanye); model BA = proyeksi skala program 3 tahun. Jangan dijumlahkan | Semua |

## 6. Temuan lain yang perlu didiskusikan

| Topik | Temuan | Pilihan |
|---|---|---|
| Baseline NBO Rp0 di halaman Profit | Bukan bug: dengan ranking produk terpopuler, kampanye rugi di setiap volume kontak, sehingga keputusan terbaik tanpa model adalah tidak berkampanye. Ranking nilai harapan (peluang × nilai − biaya) menghasilkan +Rp118 jt pada 15.284 kontak; ranking peluang saja juga rugi | Jadikan pesan presentasi: nilai muncul saat peluang digabung nilai rupiah per produk |
| Fallback agent ke template | 4 dari 45 kasus (sekitar 9%) jatuh ke template karena Gemma kadang gagal menyusun draft; saat diulang berhasil. Tool Correctness DeepEval 60% mencerminkan ini | (a) agent mencoba ulang sekali sebelum fallback, sekitar +15 detik hanya di kasus gagal; (b) cukup andalkan cache untuk entitas demo |
| Penjelasan "nasabah mirip" NBO | Median 0% dari 50 tetangga graph memegang produk yang direkomendasikan; lift rata-rata 0,34x | Sudah diputuskan: hanya ditampilkan bila lift ≥ 1,5x (sekitar 9% rekomendasi) |
| Janji di PRD yang belum dikerjakan | TaskCompletionMetric, 10 sampel cek manual DeepEval, export PPTX | Kerjakan sebelum demo atau tulis sebagai pasca-demo |
| Autodebit untuk nasabah perorangan | Katalog hanya punya versi korporasi | Tambah baris perorangan di katalog atau blokir produk korporasi untuk perorangan |
