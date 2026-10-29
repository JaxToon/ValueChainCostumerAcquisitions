# Keputusan Grill Me — RM Copilot Value Chain

Sesi grill me 9 Oktober 2026. Dokumen ini mencatat keputusan tim atas PRD dan Guideline Data Sintetis. Kalau ada yang bertentangan dengan PRD, dokumen ini yang berlaku sampai PRD diperbarui.

## Ringkasan

| # | Topik | Keputusan |
| --- | --- | --- |
| Q1 | Scope | Semua fitur dikerjakan, termasuk F12 dashboard profit |
| Q2 | Persona demo | RM Transactional segmen Commercial; Product Specialist pengguna kedua; nasabah perorangan tampil sebagai ekosistem perusahaan |
| Q3 | Urutan potong kalau telat | F16 PPTX → F18 Tanya AI → F15 monitoring penuh → F14 visual graph interaktif |
| Q4 | Target metrik | Mengalahkan baseline bisnis + batas minimal realistis (akuisisi AUC ≥ 0,65 dan PR-AUC di atas baseline nominal terbesar; NBO Precision@3 di atas produk terpopuler) |
| Q5 | Knowledge graph | Neo4j; environment sudah siap |
| Q6 | F12 | Tetap dikerjakan (tidak ditunda) |
| Q7, Q11 | Data Corporate | Data dan RM Corporate tetap ada; demo memakai RM Commercial; data harus cukup untuk train, evaluasi, dan demo |
| Q8, Q12 | Prospek | Perusahaan (NTB, non-debitur ke debitur) dan perorangan. Perorangan utamanya pedagang/pengusaha; karyawan via payroll tetap ada sebagai prospek kedua |
| Q9 | Pembelian baru NBO | Tidak dimiliki 3 bulan, lalu dimiliki di bulan berikutnya |
| Q10 | Walk-forward | NBO 4 jendela bulanan (terakhir = test). Akuisisi dan wholesale 2 jendela: validasi fitur 1–5 label 6–11, test fitur 1–11 label 12–17 |
| Q13 | Asumsi F12 | Dikerjakan Claude: cari sumber publik bila ada, sisanya ASUMSI dengan keterangan, bisa diubah lewat slider |
| Q14 | Model LLM | Generator model mini OpenAI; juri DeepEval model OpenAI lebih besar |
| Q15 | DeepEval | Faithfulness, kepatuhan pitch, agent ≥ 0,8; relevansi, RAG, alasan kontekstual ≥ 0,7. Expected_output ditulis pemegang GenAI, 10 sampel dicek anggota lain |
| Q16 | Label 2 jendela | Generator membuat label akuisisi dan wholesale di bulan 6–11 dan 12–17 |
| Q17, Q22 | Label wholesale | Base rate dinaikkan dengan proksi publik (lihat di bawah), minimal sekitar 100 label per jendela; jumlah perusahaan dinaikkan |
| Q18, Q21, Q26 | Produk untuk ML | Semua produk yang datanya dibangkitkan: ritel, wholesale, UMKM/pedagang (Tabungan Plus Bisnis, QRIS, EDC, KUR). Anak usaha dan kanal digital keluar, kecuali mobile banking, QRIS, EDC. API hanya ditawarkan lewat aturan untuk Corporate besar. Rekening utama (Tabungan Plus, Tabungan Plus Muda, Tabungan Plus Anak) tidak direkomendasikan karena berganti mengikuti umur |
| Q19 | Pedagang | Sekitar 8.000 pedagang (ASUMSI) membeli dari distributor/anchor Bank. Produk pembuka: Tabungan Plus Bisnis → QRIS → KUR Mikro. Dihubungi hanya lewat program anchor |
| Q20, Q23, Q27 | Corporate sedikit | Data Corporate tetap proporsional; oversampling hanya di data train saat melatih model (class_weight atau random oversampling); validasi dan test tetap asli; tanpa SMOTE |
| Q24 | Anchor demo | Dipilih otomatis: anchor Corporate dengan mitra Commercial terbanyak, porsi dana ke bank lain terbesar, minimal 1 sinyal pindah bank dan 1 peluang reaktivasi |
| Q25 | Ambang F19 | Counterpart baru ≥ Rp100 juta/bulan; berulang ≥ 3 dari 6 bulan; transaksi besar = 5% teratas per perusahaan; pindah bank = porsi nama sama/bank beda naik ≥ 20 poin vs rata-rata 3 bulan |
| Q28 | Demo | Skrip 7 menit + versi darurat 3 menit, satu cerita RM Commercial (lihat di bawah) |
| Q29 | Peran | Mengikuti PRD bagian 15; nama anggota belum ditetapkan |
| Q30 | Fallback | Cache output LLM; app hanya membaca file hasil (tidak bergantung Neo4j menyala); video demo 3 menit; 3 skenario guardrail dilatih minimal 3 kali |

## Proksi publik untuk kalibrasi label

| Label | Proksi | Sumber |
| --- | --- | --- |
| Cross-sell layanan transaksi | Pengguna CIB cash 261.815 per Des 2025, naik 24,8% setahun (sekitar 11% per 6 bulan) | Bisnis.com |
| Non-debitur ke debitur | Kredit korporasi Bank +10,4% YoY (S1 2025); nasional kredit investasi +17,98%, modal kerja +2,04% YoY (Nov 2025) | Investortrust, [IDX Channel](https://www.idxchannel.com/banking/kredit-perbankan-november-2025-capai-rp8314-triliun-tumbuh-774-persen/all) |
| KUR untuk UMKM | KUR Bank Rp10,6 triliun ke sekitar 46 ribu UMKM per Okt 2025 | Kontan |
| QRIS untuk pedagang | 39,3 juta merchant QRIS per semester I 2025 | [Kontan](https://keuangan.kontan.co.id/news/bi-sebut-pengguna-qris-tembus-57-juta-orang-per-semester-i-2025) |
| Reaktivasi, leakage | Tidak ada data publik; ASUMSI | — |

Jumlah debitur atau nasabah korporasi Bank tidak dipublikasikan di sumber yang ditemukan; dicek lagi di Laporan Tahunan Bank 2025.

## Skrip demo (7 menit)

1. Dashboard Peluang RM: lead baru dari anchor showcase (F21, F19)
2. Detail prospek: jalur graph, skor, alasan (F4–F6)
3. Tombol "Siapkan bahan kunjungan": agent menyusun paket H-1 (F17, F22)
4. Guardrail: prompt jahat ditolak, kartu kredit untuk nasabah 16 tahun dicoret, ID tersamar
5. RM menyetujui, tercatat di log
6. Dashboard profit: nilai rupiah (F12)

Halaman KPI, ekosistem, dan model ditunjukkan sekilas atau saat Q&A. Versi 3 menit: langkah 1, 3, 4, 6.

## Hasil cek data sebelum perubahan (run 9 Okt 2026)

| Bagian | Jumlah label | Status |
| --- | --- | --- |
| NBO pembelian baru | sekitar 2.000 per bulan | Cukup; Fleksi 8, KPR 30, reksa dana 63 dalam 14 bulan |
| Akuisisi | 260 perusahaan, 855 orang | Hanya di bulan 12–17, belum ada jendela validasi |
| Cross-sell wholesale | 156 | Pas-pasan |
| Reaktivasi | 76 | Kurang |
| Non-debitur ke debitur | 41 | Kurang |
| Leakage | 82 (Commercial 13) | Kurang untuk Commercial |

## Pertanyaan yang masih terbuka (perlu RM, PS, atau Bank)

- Batas omzet segmen Commercial (Rp10–150 miliar) dan RCC: siapa yang mengonfirmasi
- KPI keberhasilan sistem (waktu persiapan, konversi NTB, non-debitur ke debitur, cross-sell, wallet share)
- Jadwal kunjungan debitur vs non-debitur (minggu 1 saja atau minggu 1–2)
- Aturan pemetaan kebutuhan ke produk (F20) perlu dicek RM dan PS
- Definisi resmi SKB dan DLN
- Nama anggota per peran dan siapa yang menjalankan demo

## Pekerjaan lanjutan dari keputusan ini

1. Generator: label 2 jendela, pedagang, produk UMKM (QRIS, EDC, KUR), kalibrasi base rate, jumlah perusahaan dinaikkan
2. Validasi: cek label per jendela, cek pedagang, cek produk UMKM
3. PRD dan Guideline diperbarui sesuai keputusan, lalu diekspor ulang ke docs/
4. Asumsi F12 (margin, nilai nasabah baru, biaya kontak) dengan sumber publik bila ada

## Perubahan setelah grill me (9–12 Oktober 2026)

Keputusan di atas tetap dicatat apa adanya. Yang berubah sesudahnya, dengan alasannya:

| Keputusan awal | Perubahan | Tanggal | Alasan |
|---|---|---|---|
| Q14: generator model mini OpenAI; juri model OpenAI lebih besar | Generator Gemma 4 E4B lokal lewat Ollama; OpenAI hanya untuk juri DeepEval (`gpt-4.1-mini`) | 9 Okt | Data tidak keluar dari laptop (UU PDP), gratis dan offline saat demo; kredit OpenAI hanya $8, cukup untuk evaluasi |
| Q14: juri DeepEval model besar (GPT-4.1) | Juri `gpt-4.1-mini` | 9 Okt | Satu run 45 kasus sekitar $0,28; tetap jauh lebih besar dari generator dan berbeda keluarga model |
| Q15: skor final rata-rata 3 run | Dijalankan: output yang sama dinilai juri 3 kali, 96% lolos (95–97%) | 12 Okt | Sesuai keputusan; 10 sampel cek manual belum dilakukan |
| Q20/Q23/Q27: class_weight atau random oversampling di data train | Keduanya diuji berdampingan sebagai kandidat; yang menang di validasi dipakai (karyawan memakai oversampling, mesin lain class weights) | 10 Okt | Bukti terukur untuk memilih, bukan asumsi |
| PRD: login dan role user tidak dibuat | Login demo sederhana dan dashboard per peran (RM Retail, RM Wholesale/Corporate, Manajemen) | 12 Okt | Masukan tim: setiap pengguna melihat dashboard yang relevan |
| Q30: app tidak bergantung Neo4j | Tetap; ditambah Docker (app, Ollama, Neo4j) supaya tim cukup `docker compose up` | 12 Okt | Masukan tim: BA dan DE bisa menjalankan tanpa instalasi manual |
| Penjelasan "nasabah mirip" untuk NBO | Hanya ditampilkan bila lift tetangga ≥ 1,5x | 10 Okt | Median 0% dari 50 tetangga memegang produk yang direkomendasikan; kalimat itu justru melemahkan rekomendasi |
| Guardrail input berbasis aturan | Ditambah klasifikasi semantik oleh Gemma | 10 Okt | Regex hanya menangkap 2 dari 4 serangan baru; dengan Gemma 4/4 |
| F16 Generator PPTX (nilai tambah) | Belum dibuat, ditunda setelah demo | 12 Okt | Prioritas waktu |

Temuan yang perlu diputuskan tim ada di `docs/Rekonsiliasi_Angka_BA.md` bagian 5 dan 6.
