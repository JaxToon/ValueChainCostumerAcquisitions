# Asumsi Business Impact (F12)

Dipakai dashboard profit dan potential loss (PRD bagian 11). Setiap angka diberi status **PROKSI** (diturunkan dari data publik, sumber di bawah) atau **ASUMSI** (tidak ada data publik, dipilih tim). Semua angka bisa diubah lewat slider; hasil dashboard disebut simulasi karena datanya sintetis. Versi yang bisa dibaca kode ada di [asumsi_f12.csv](asumsi_f12.csv).

## Rumus nilai per produk

| Jenis produk | Nilai tahunan bagi bank | Contoh produk |
| --- | --- | --- |
| Kredit | Baki debet rata-rata x spread kredit | KMK, KI, KUR, SCF, KPR, Fleksi, kartu kredit |
| Dana | Saldo rata-rata x spread dana | Giro, Deposito, Tabungan Plus, Tabungan Plus Bisnis |
| Fee | Fee tahunan per nasabah | CIB, VA, L/C, SKBDN, SBLC, Garansi Bank, QRIS, EDC, reksa dana, bonds |

Untuk nasabah korporasi, baki debet dan saldo diambil dari data (`fasilitas_pembiayaan.csv`, `saldo_bulanan.csv`). Untuk nasabah perorangan, data saldo tidak dibangkitkan, jadi dipakai saldo atau plafon rata-rata ASUMSI di tabel di bawah.

## Parameter utama

| Parameter | Nilai | Status | Dasar |
| --- | --- | --- | --- |
| Spread kredit | 4,5% per tahun | PROKSI | Pendapatan bunga bersih Bank Rp40,33 T dibagi kredit Rp899,53 T (FY2025) |
| Spread dana | 2,0% per tahun dari saldo | ASUMSI | Selisih imbal hasil aset dan biaya dana; tidak ada angka publik per produk |
| Pengali risiko kredit (expected loss) | 1,5% per tahun dari baki debet | ASUMSI | Mengurangi nilai kredit; NPL Bank sekitar 1,9% disebut di media, tidak dipakai langsung |
| Biaya kunjungan RM per prospek wholesale | Rp750 ribu | ASUMSI | Waktu RM setengah hari + transport; slider Rp250 ribu sampai Rp2 juta |
| Biaya kontak nasabah ritel | Rp15 ribu | ASUMSI | Telepon atau kunjungan cabang singkat; slider Rp5 ribu sampai Rp50 ribu |
| Biaya kontak pedagang lewat program anchor | Rp50 ribu | ASUMSI | Biaya program anchor dibagi per pedagang |
| Biaya salah jual (yang dicegah guardrail) | Rp2 juta per kasus | ASUMSI | Komplain, pembatalan, risiko reputasi |
| Pengali skenario makro (bunga turun / tetap / naik) | 1,1 / 1,0 / 0,9 dari konversi kredit | ASUMSI | Slider |
| Skenario konservatif / moderat / optimis | 0,7 / 1,0 / 1,3 dari konversi | ASUMSI | Slider |

## Nilai tahunan per produk

| Produk | Basis | Nilai per tahun | Status |
| --- | --- | --- | --- |
| KMK, KI, SCF (korporasi) | Baki debet dari data x (4,5% - 1,5%) | Dari data | PROKSI + ASUMSI |
| KUR Mikro, KUR Kecil | Baki debet dari data x (4,5% - 1,5%) | Dari data | PROKSI + ASUMSI |
| Giro, Deposito Non Perorangan | Saldo rata-rata dari data x 2% | Dari data | ASUMSI |
| CIB, CIB Cash/Receivables/Supply Chain | Fee tahunan | Rp6 juta | ASUMSI |
| Virtual Account (Kredit, Debit) | Fee tahunan | Rp12 juta | ASUMSI |
| Impor/Ekspor L/C, SKBDN, SBLC, Garansi Bank | 0,5% dari nilai proyek | Dari data | ASUMSI |
| Cash Pooling, Account Sweep | Fee tahunan | Rp24 juta | ASUMSI |
| Payroll Korporasi | Rp100 ribu x jumlah karyawan | Dari data | ASUMSI |
| QRIS Bank | Fee tahunan per merchant | Rp300 ribu | ASUMSI |
| EDC Bank | Fee tahunan per merchant | Rp1,2 juta | ASUMSI |
| Tabungan Plus Bisnis | Saldo rata-rata Rp15 juta x 2% | Rp300 ribu | ASUMSI |
| Tabungan Plus, Tabungan Plus Muda | Saldo rata-rata Rp5 juta x 2% | Rp100 ribu | ASUMSI |
| Bank Deposito (perorangan) | Saldo rata-rata Rp100 juta x 2% | Rp2 juta | ASUMSI |
| Bank Giro (perorangan) | Saldo rata-rata Rp50 juta x 2% | Rp1 juta | ASUMSI |
| Mobile Banking | Fee transaksi dan biaya layanan yang lebih rendah | Rp60 ribu | ASUMSI |
| Bank Payroll (perorangan) | Saldo gaji rata-rata Rp4 juta x 2% | Rp80 ribu | ASUMSI |
| Bank Visa Platinum | Fee tahunan + bunga dari outstanding Rp8 juta x 4,5% | Rp660 ribu | ASUMSI |
| KPR Pembelian | Outstanding Rp400 juta x (4,5% - 1,5%) | Rp12 juta | ASUMSI |
| Bank Fleksi | Outstanding Rp60 juta x (4,5% - 1,5%) | Rp1,8 juta | ASUMSI |
| DPLK Pensiun | Fee pengelolaan | Rp150 ribu | ASUMSI |
| Reksa Dana (agen penjual), Bonds | 0,5% dari dana Rp25 juta | Rp125 ribu | ASUMSI |
| Autodebit | Fee tahunan | Rp24 ribu | ASUMSI |
| Prioritas | Saldo dana kelolaan Rp500 juta x 2% | Rp10 juta | ASUMSI |

## Nilai tahun pertama nasabah baru (akuisisi)

| Tipe prospek | Rumus | Status |
| --- | --- | --- |
| Perusahaan (NTB) | Nilai produk pertama (Giro atau Tabungan Plus Bisnis dari saldo data) + rata-rata nilai produk nasabah sejenis di segmen yang sama x 50% | ASUMSI (50% = hanya sebagian wallet pindah di tahun pertama, sesuai interview: "product acquisition tidak sama dengan immediate wallet acquisition") |
| Pedagang | Tabungan Plus Bisnis Rp300 ribu + peluang QRIS 30% x Rp300 ribu | ASUMSI |
| Karyawan (via payroll) | Tabungan Plus atau Tabungan Plus Muda Rp100 ribu + Bank Payroll Rp80 ribu | ASUMSI |

## Rumus dashboard

- Pendapatan kotor = jumlah prediksi benar x nilai produk (cross-sell) atau nilai tahun pertama (akuisisi)
- Biaya = jumlah dihubungi x biaya kontak atau kunjungan
- Profit bersih = pendapatan kotor - biaya
- Kerugian potensial: usaha sia-sia (prediksi salah x biaya kontak), peluang terlewat (pembeli yang tidak ditawari x nilai), salah jual yang dicegah (kasus diblokir guardrail x biaya salah jual)
- Semua dibandingkan dengan baseline bisnis: produk terpopuler (NBO) dan nominal transfer terbesar (akuisisi)

## Sumber

- Kontan, 3 Februari 2026: Bank bukukan laba bersih Rp20 triliun pada 2025, fee based income menopang pendapatan (pendapatan bunga bersih Rp40,33 T, kredit Rp899,53 T, fee-based income Rp18,46 T, CASA Rp725,96 T)
- Margin per produk, biaya kunjungan, dan biaya kontak Bank tidak dipublikasikan; semuanya ASUMSI dan wajib disebut di slide.
