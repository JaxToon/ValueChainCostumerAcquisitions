# Implementasi Komponen Awal GenAI dan RAG

Dokumen ini menjelaskan bagian GenAI RM Copilot: model bahasa yang dipakai, RAG atas katalog produk Bank, agent penyusun paket kunjungan (F17/F22), Tanya AI (F18), dan cara kualitasnya diukur. Guardrail dijelaskan terpisah di `docs/Implementasi_Guardrail.md`.

Kode utama ada di `src/genai/`: `llm.py`, `rag.py`, `tools.py`, `agent.py`, `tanya.py`, `prompts.py`.

## 1. Peran GenAI di sistem

GenAI tidak membuat rekomendasi sendiri. Model ML yang memilih produk dan prospek; GenAI menjelaskan dan menyiapkan bahan untuk RM.

| Fitur | Pemicu | Keluaran | Halaman |
|---|---|---|---|
| Paket kunjungan H-1 (F17 agent → F22) | tombol "Siapkan bahan kunjungan", tanpa teks bebas | ringkasan bisnis dan transaksi, peluang produk beserta alasan dan sumber, pertanyaan validasi, sudut pitching, stakeholder, draft pitch untuk nasabah | Peluang RM, Rekomendasi nasabah, Prospek |
| Tanya AI (F18) | pertanyaan teks dari RM | jawaban singkat dari katalog Bank dengan URL sumber | Tanya AI produk |

Semua keluaran adalah **draft**. RM memilih Setujui, Edit, atau Tolak, dan keputusannya dicatat di audit log.

## 2. Model bahasa

| Aspek | Pilihan | Alasan |
|---|---|---|
| Generator | Gemma 4 E4B (`google/gemma-4-E4B-it`, lisensi Apache 2.0) lewat Ollama, tag `gemma4:e4b`, kuantisasi 4-bit | gratis, berjalan lokal di GPU laptop 8 GB, mendukung function calling, data tidak keluar dari laptop (UU PDP) |
| Cara memanggil | SDK OpenAI ke API kompatibel Ollama (`http://localhost:11434/v1`) | satu kode untuk Ollama dan OpenAI; ganti lewat `llm.provider` di `config/settings.yaml` |
| Mode berpikir | dimatikan (`reasoning_effort: none`) | sekitar 2x lebih cepat; jawaban pendek 13,7 → 6,6 detik |
| Model tetap dimuat | `keep_alive: 30m` + warm-up di latar belakang saat app dibuka | klik pertama tidak menunggu model dimuat |
| Temperature | 0,2 | jawaban konsisten tapi tidak kaku |
| Timeout | 60 detik, tanpa retry | lebih baik cepat jatuh ke template daripada membuat RM menunggu |
| Juri evaluasi | `gpt-4.1-mini` (OpenAI), hanya untuk DeepEval | jauh lebih besar dari generator dan berbeda keluarga model; kredit evaluasi hanya $8 |

**Cache.** Jawaban LLM disimpan di `data/processed/llm_cache.json`, dengan kunci entitas + nama model, sehingga mengganti model tidak memakai jawaban model lain. Cache juga menyimpan langkah tool, supaya paket dari cache tetap menunjukkan konteksnya. Jawaban template tidak di-cache, jadi LLM dicoba lagi di klik berikutnya. `python -m pipelines.warm_demo` menyiapkan cache untuk entitas yang muncul di demo.

**Fallback.** Bila Ollama tidak terjangkau atau draft tidak bisa dipakai, sistem menjalankan rencana tetap dengan tool yang sama dan mengisi template. Demo tidak pernah berhenti karena LLM. `tests/test_fallback.py` menguji ini dengan Ollama dibuat "mati".

## 3. RAG atas katalog produk Bank

Sumber pengetahuan: `synthetic_generator/reference/produk_bank_knowledge.csv`, berisi 216 produk Bank dengan kolom fungsi dan manfaat, target nasabah, kapan direkomendasikan, kapan tidak cocok, syarat umum, dan URL sumber.

| Langkah | Implementasi (`src/genai/rag.py`) |
|---|---|
| Teks yang diindeks | gabungan `Nama_Produk`, `Kategori`, `Sub_Kategori`, `Fungsi_Manfaat`, `Target_Nasabah`, `Rekomendasikan_Jika`, `Syarat_Umum` |
| Normalisasi | huruf kecil + sinonim untuk istilah yang terpecah tokenizer: `l/c` → "lc letter of credit", `importir` → "impor", `eksportir` → "ekspor", `skbdn`, `bank garansi`, `jaminan pelaksanaan` |
| Retrieval | TF-IDF unigram + bigram, `sublinear_tf`, kemiripan kosinus; tanpa vector database |
| Pencarian nama produk | nama yang persis sama dicari dulu, baru TF-IDF, supaya "Bank Deposito" tidak tertukar dengan "Bank Deposito Non Perorangan" |
| Filter | segmen Anak Usaha, Digital & E-Banking, dan API/Open Banking tidak direkomendasikan (grill me Q21/Q26), kecuali mobile banking, QRIS, dan EDC; API hanya untuk nasabah Corporate |
| Sitasi | setiap produk yang disebut wajib membawa `URL_Sumber` dari baris katalog yang ditemukan |

Kenapa TF-IDF dan bukan embedding: katalog kecil (216 baris), istilahnya sangat spesifik (KUR, SKBDN, CIB), hasilnya bisa dijelaskan, dan tidak perlu layanan tambahan saat demo. Kelemahannya (istilah terpecah, variasi kata) ditangani dengan sinonim dan pencarian nama persis; keduanya ditemukan lewat DeepEval.

## 4. Enam tool hanya-baca

Agent hanya boleh memanggil tool ini (`src/genai/tools.py`). Tidak ada tool yang menulis ke sistem, mengirim pesan, atau membuka rekening.

| Tool | Fungsi |
|---|---|
| `ambil_profil` | profil nasabah atau prospek: sektor, segmen, riwayat produk, fasilitas, saldo 3 bulan, sinyal F19, ringkasan transaksi |
| `skor_produk` | produk kandidat dari model ML beserta alasan SHAP; untuk nasabah wholesale, produk berbasis kebutuhan (banyak pembayar, banyak penerima, trade, rantai pasok, UMKM) |
| `cek_kelayakan` | syarat katalog dan regulator untuk satu atau beberapa produk sekaligus (usia, penghasilan, pekerjaan, segmen, umur usaha) |
| `cari_katalog` | pencarian RAG; menerima teks bebas atau daftar nama produk |
| `cek_compliance` | cek kebocoran data dan footer OJK pada teks |
| `susun_draft` | menyerahkan paket final dalam skema terstruktur |

`susun_draft` memakai skema JSON bertipe: `peluang` adalah daftar objek `{produk, alasan, sumber}`, sedangkan pertanyaan validasi, sudut pitching, dan stakeholder adalah daftar teks. Draft yang tidak sesuai skema dinormalisasi; bila `peluang` tetap tidak terstruktur, sistem jatuh ke template.

## 5. Agent penyusun paket kunjungan

Alur di `src/genai/agent.py`:

1. System prompt (`prompts.AGENT`) memberi urutan kerja: `ambil_profil` → `skor_produk` → `cek_kelayakan` untuk semua kandidat sekaligus → `cari_katalog` untuk yang layak → `susun_draft`.
2. Model memilih tool di setiap langkah lewat function calling, maksimal 6 langkah. Hasil tool disamarkan (ID, nomor, telepon, email) sebelum dikirim balik ke model.
3. Di langkah terakhir hanya `susun_draft` yang ditawarkan, ditambah instruksi `prompts.FINAL_STEP`. Tanpa ini Gemma kadang menghabiskan semua langkah untuk mencari data.
4. Panggilan tool yang salah (nama tidak ada atau argumen keliru) dikembalikan ke model sebagai pesan error, bukan menghentikan agent.
5. Paket dicek guardrail output: produk harus ada di katalog, layak untuk nasabah ini, dan berasal dari rekomendasi model (produk yang ditambahkan LLM sendiri dicoret). Pitch dibersihkan dan diberi footer OJK.
6. Paket, langkah tool, dan hasil guardrail ditulis ke audit log, lalu ditampilkan dengan tombol Setujui / Edit / Tolak.

Waktu di GPU laptop (RTX 5050): 15–27 detik per paket; dari cache kurang dari 1 detik.

## 6. Tanya AI

Alur di `src/genai/tanya.py`:

1. Guardrail input aturan (pola injeksi, permintaan data pihak lain, topik, masking).
2. Bila lolos aturan, Gemma mengklasifikasi pertanyaan (aman, injeksi, data pihak lain, di luar topik). Hanya "aman" yang diteruskan.
3. RAG mengambil 3 produk paling relevan. Bila tidak ada yang cocok, jawabannya "Saya tidak tahu. Produk yang sesuai tidak ditemukan di katalog Bank."
4. Gemma menjawab singkat hanya dari baris katalog itu, dengan URL sumber.
5. Jawaban dicek kebocoran data, lalu dicatat di audit log.

Waktu sekitar 16 detik per pertanyaan baru.

## 7. Evaluasi kualitas (DeepEval)

Golden set 50 kasus (`tests/golden/llm_cases.jsonl`): 15 nasabah NBO (termasuk usia di bawah 17 dan penghasilan rendah), 10 prospek value chain, 10 paket wholesale, 5 jalannya agent, 5 pertanyaan Tanya AI, dan 5 serangan. Output generator dibuat sekali, lalu dinilai juri 3 kali (`python -m tests.eval_report --runs 3`).

| Metrik | Lolos (rata-rata 3 run) |
|---|---|
| Faithfulness (jawaban sesuai konteks tool/katalog) | 100% |
| Relevansi jawaban | 100% |
| Kepatuhan pitch (footer OJK, tanpa data pihak lain, tanpa janji imbal hasil) | 100% |
| PII leakage pada pitch | 98% |
| Alasan kontekstual (alasan menyebut sinyal nyata dan memberi pertanyaan validasi) | 87% (82–90%) |
| Tool correctness agent | 60% |
| **Semua penilaian** | **96% (95–97%)** |

Tool correctness 60% mencerminkan fallback, bukan pemilihan tool yang salah: di 2 dari 5 kasus agent, Gemma gagal menyusun draft lalu sistem jatuh ke template. Secara keseluruhan sekitar 9% kasus (4 dari 45) jatuh ke template; saat diulang kasus yang sama berhasil.

Perbaikan yang lahir dari evaluasi: pencarian nama produk persis, sinonim L/C dan importir, rubrik kepatuhan yang diperjelas, PII dinilai pada pitch eksternal, dan guardrail janji imbal hasil. Rincian per kasus ada di `docs/Hasil_DeepEval.md`.

## 8. Keterbatasan dan langkah berikutnya

- Fallback ke template sekitar 9%; opsi perbaikan: agent mencoba ulang sekali sebelum fallback.
- `expected_output` golden set belum diisi tim, dan 10 sampel cek manual dari PRD belum dilakukan.
- Di laptop tanpa GPU (misalnya lewat Docker di CPU), Gemma jauh lebih lambat; demo mengandalkan cache dan fallback.
- TF-IDF bergantung pada kata; pertanyaan dengan istilah yang sangat berbeda dari katalog bisa tidak ditemukan.
