# Panduan Uji Pengguna lewat ngrok

Untuk anggota tim yang menjalankan sesi uji: dashboard dijalankan di laptop tim, lalu dibuka oleh penguji (misalnya RM) lewat link ngrok dari mana saja. Masukan penguji tersimpan otomatis di aplikasi.

## 1. Persiapan (sekali)

1. Pasang ngrok:

   ```powershell
   winget install ngrok.ngrok
   ```

   Atau unduh dari ngrok.com/download.
2. Daftar akun gratis di dashboard.ngrok.com, salin **authtoken**, lalu:

   ```powershell
   ngrok config add-authtoken <TOKEN-ANDA>
   ```

## 2. Sebelum sesi uji

1. Pastikan Ollama berjalan (`ollama list` menampilkan `gemma4:e4b`).
2. Siapkan cache entitas demo supaya klik pertama penguji tidak menunggu (sekitar 5 menit):

   ```powershell
   cd D:\Project\BuatCapstone\ValueChainAccusition
   .\.venv\Scripts\python -m pipelines.warm_demo
   ```

3. Jalankan dashboard dengan **password khusus sesi uji**. Password demo `demo123` tertulis di README, jadi untuk link publik semua akun diganti sementara ke password yang hanya dikirim ke penguji, dan petunjuk password di halaman login disembunyikan:

   ```powershell
   $env:RM_COPILOT_PASSWORD = "GantiDenganKataSandiSesiUji"
   .\.venv\Scripts\streamlit run app/Home.py --server.port 8502
   ```

   Setelah sesi, tutup jendela ini; menjalankan aplikasi biasa kembali memakai `demo123`.
4. Di jendela PowerShell lain, buka tunnel:

   ```powershell
   ngrok http 8502
   ```

   **Jangan memakai `--basic-auth` ngrok.** Kata sandi ngrok ikut memblokir koneksi WebSocket Streamlit, sehingga penguji hanya melihat halaman putih kosong. Perlindungannya ada di password sesi uji (langkah 3).
5. Salin alamat **Forwarding** (`https://....ngrok-free.dev`) dan kirim ke penguji bersama:
   - akun sesuai peran penguji (misalnya `rm.wholesale`) dan password sesi uji,
   - skenario di bagian 3.

Catatan untuk penguji: ngrok gratis menampilkan halaman peringatan "You are about to visit" lebih dulu; klik **Visit Site**.

Jaringan laptop harus stabil selama sesi. Bila koneksi laptop putus, tunnel tersambung ulang otomatis dengan alamat yang sama, tetapi penguji perlu memuat ulang halaman.

## 3. Skenario untuk penguji

Kirim teks ini ke penguji. Mintalah ia mengerjakan tanpa dibantu, sambil mengatakan apa yang dipikirkannya (bila lewat video call). Waktu: sekitar 15 menit.

> Anda adalah RM Wholesale yang memegang portofolio nasabah Commercial. Masuk dengan akun yang kami kirim, lalu kerjakan:
>
> 1. **Tentukan nasabah yang paling perlu dikunjungi minggu ini.** Siapa, dan kenapa?
> 2. **Siapkan bahan kunjungan untuk nasabah itu.** Baca produk yang disarankan dan pertanyaannya. Apakah masuk akal? Setujui, ubah, atau tolak pesan untuk nasabah.
> 3. **Cari satu calon nasabah dari transaksi nasabah Anda.** Di mana lokasinya, dan siapa yang bisa Anda hubungi untuk visit?
> 4. **Lihat mitra (supplier dan buyer) anchor PT Anchor 0033.** Berapa yang sudah nasabah Bank, dan berapa close loop-nya?
> 5. **Tanyakan satu hal tentang produk Bank di Tanya AI.**
>
> Setelah selesai, klik **Beri masukan** di sidebar kiri dan isi apa yang membingungkan, apa yang berguna, serta saran Anda.

Untuk penguji RM Retail (akun `rm.retail`), ganti langkah 1–4 dengan:

> 1. Tentukan nasabah perorangan yang paling siap ditawari produk, dan produk apa.
> 2. Cek apakah ada produk yang tidak boleh ditawarkan ke nasabah itu, dan kenapa.
> 3. Siapkan bahan kunjungan dan putuskan pesannya.

Yang perlu dicatat pengamat: di langkah mana penguji ragu atau salah klik, istilah yang tidak dipahami, dan berapa lama setiap langkah.

## 4. Setelah sesi

1. Hentikan tunnel dengan `Ctrl+C` di jendela ngrok. Link langsung tidak bisa dibuka lagi.
2. Baca masukan:
   - di aplikasi: masuk sebagai `manajemen` → **Log dan guardrail** → bagian **Masukan pengguna**,
   - atau file `outputs/masukan_pengguna.csv`.
3. Keputusan penguji (Setujui/Edit/Tolak) dan pertanyaan Tanya AI tercatat di halaman **Log dan guardrail**.

## 5. Keamanan

- Selama tunnel menyala, siapa pun yang punya link **dan** kata sandi ngrok bisa membuka dashboard. Bagikan hanya ke penguji, dan matikan tunnel setelah sesi.
- Semua data di aplikasi sintetis; tidak ada data nasabah sungguhan.
- Penguji memakai Gemma di laptop tim; pertanyaan Tanya AI tetap melewati guardrail dan tercatat di log.
- File `.env` (API key) tidak bisa diakses lewat dashboard, tetapi jangan pernah membagikannya.
