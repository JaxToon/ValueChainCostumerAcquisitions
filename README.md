# Value Chain RM Copilot — Relationship & Value Chain Intelligence

Copilot untuk Relationship Manager (RM) bank segmen Commercial: menemukan calon nasabah yang sebenarnya sudah bertransaksi dengan nasabah yang ada (supplier, buyer, karyawan), memprioritaskannya, lalu menyiapkan bahan kunjungan.

Knowledge graph (Neo4j + GDS) + ML (akuisisi, wholesale, next-best-offer) + GenAI lokal (Gemma 4 E4B via Ollama) + guardrail 4 lapis + dashboard Streamlit per peran.

> Semua data **sintetis**, dikalibrasi ke statistik publik (BPS, OJK, KSEI) dan dataset Santander di Kaggle. "Bank" hanyalah nama placeholder; ini proyek capstone/portofolio pribadi dan tidak berafiliasi dengan bank mana pun.

Dokumen utama: [PRD](docs/PRD.md), [Guideline data sintetis](docs/Guideline_Data_Sintetis.md), [keputusan desain](docs/Grill_Me_Keputusan.md), [hasil model](docs/Hasil_Model.md), [hasil DeepEval](docs/Hasil_DeepEval.md), [kamus project](docs/Kamus_Project.md).

Penjelasan implementasi: [baseline model ML](docs/Implementasi_Baseline_ML.md), [GenAI dan RAG](docs/Implementasi_GenAI_RAG.md), [guardrail](docs/Implementasi_Guardrail.md). Business case: [asumsi dampak bisnis](docs/Asumsi_Business_Impact.md), [rekonsiliasi angka](docs/Rekonsiliasi_Angka_BA.md).

## Cara tercepat: Docker

Uji coba oleh pengguna (skenario tugas dan pengumpulan masukan): [docs/Panduan_Uji_Pengguna.md](docs/Panduan_Uji_Pengguna.md).

Butuh [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows: WSL2 aktif), RAM 16 GB disarankan, dan sisa disk sekitar 20 GB.

```powershell
git clone https://github.com/JaxToon/value-chain-rm-copilot.git
cd value-chain-rm-copilot
docker compose up -d --build
```

Buka `http://localhost:8501` dan masuk dengan akun demo (lihat "Login per peran").

- **Data.** Container app membangun data sendiri saat pertama jalan (generator + Neo4j + pipeline, sekitar 30–60 menit, sekali saja). Pantau dengan `docker compose logs -f app`.
- **Model LLM.** Service `ollama-pull` mengunduh `gemma4:e4b` (6,6 GB) sekali. Selama belum selesai, jawaban memakai template.
- **GPU NVIDIA (opsional).** `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`. Tanpa GPU, Gemma berjalan di CPU dan jauh lebih lambat; entitas demo yang sudah ada di cache tetap instan.
- **Neo4j Browser** untuk melihat graph: `http://localhost:7474` (user `neo4j`, password `rmcopilot-demo`). Setelah data jadi, Neo4j boleh dihentikan untuk menghemat RAM: `docker compose stop neo4j`.
- **Perintah lain:** `docker compose run --rm app python -m pytest tests -q -k "not kualitas"` (tes), `docker compose run --rm app pipeline` (bangun ulang data), `docker compose down` (berhenti).

## Login per peran

Dashboard menampilkan beranda dan halaman yang berbeda per peran. Password semua akun demo: `demo123`.

| Username | Peran | Halaman |
|---|---|---|
| `rm.retail` | RM Retail | beranda nasabah prioritas, rekomendasi nasabah (NBO), prospek pedagang dan karyawan, Tanya AI |
| `rm.wholesale` | RM Wholesale / Corporate | beranda portofolio, Peluang RM, prospek perusahaan, ekosistem anchor, Tanya AI |
| `manajemen` | Manajemen / Stakeholder | beranda bisnis (potensi profit per program, aktivitas dihubungi/deal per RM, peluang per kanwil), profit dan potential loss, ekosistem; tata kelola: model dan monitoring, KPI model, log dan guardrail |

Akun ada di `config/settings.yaml` (`akun_demo`, password disimpan sebagai SHA-256). Login ini hanya memilih tampilan, bukan sistem keamanan produksi.

## Yang perlu dipasang

| Kebutuhan | Untuk | Catatan |
|---|---|---|
| Python 3.11 | semua | `py -3.11 --version` |
| [Ollama](https://ollama.com/download) + model `gemma4:e4b` (6,6 GB) | jawaban LLM di dashboard | Tanpa Ollama dashboard tetap jalan, jawaban pakai template |
| Neo4j Desktop 2 + plugin Graph Data Science | hanya untuk membangun data | Tidak perlu untuk menjalankan dashboard |
| OpenAI API key | hanya untuk DeepEval (juri `gpt-4.1-mini`) | Tidak perlu untuk demo |

## Persiapan (sekali)

```powershell
git clone https://github.com/JaxToon/value-chain-rm-copilot.git
cd value-chain-rm-copilot
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # isi password Neo4j / OpenAI key bila perlu
ollama pull gemma4:e4b
```

Folder `data/`, `outputs/`, dan `synthetic_generator/output/` tidak masuk git (besar), jadi dibangun dari nol dengan langkah berikut.

## Membangun data

Hasilnya deterministik karena seed tetap (`seed: 42`).

1. **Data sintetis** (sekitar 3 menit):
   ```powershell
   cd synthetic_generator
   python run.py
   cd ..
   ```
2. **Neo4j**: di Neo4j Desktop buat DBMS baru, pasang plugin Graph Data Science, lalu Start. Isi `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` di `.env`.
3. **Pipeline offline** (clean, ingest Neo4j, algoritma graph, fitur, model, SHAP, laporan):
   ```powershell
   python -m pipelines.run_offline
   ```
   Bila gagal di tengah, lanjutkan dari langkah itu, misalnya `python -m pipelines.run_offline --from features`.

## Menjalankan dashboard

Pastikan Ollama jalan (ikon di system tray, cek dengan `ollama list`). Neo4j tidak perlu.

```powershell
.\.venv\Scripts\streamlit run app/Home.py
```

Buka `http://localhost:8501`, masuk dengan akun demo. Sebelum demo, siapkan cache entitas yang akan diklik: `python -m pipelines.warm_demo`. Klik pertama "Siapkan bahan kunjungan" sekitar 15–30 detik (Gemma dimuat ke GPU); klik berikutnya untuk entitas yang sama langsung dari cache. Badge "Mode: template" berarti Ollama tidak terjangkau.

Ganti ke OpenAI sebagai generator: di `config/settings.yaml` ubah `llm.provider` ke `openai` dan `model_generator` ke `gpt-4.1-mini`.

## Tes dan evaluasi

```powershell
python -m pytest tests -q -k "not kualitas"   # guardrail, no-lookahead, serangan (gratis)
python -m tests.eval_report                   # DeepEval 45 kasus, butuh OPENAI_API_KEY, sekitar $0,28
```

## Struktur

| Folder | Isi |
|---|---|
| `synthetic_generator/` | generator data sintetis + referensi resmi (BPS, OJK, KSEI, BI, katalog Bank) |
| `src/` | data cleaning, graph (Neo4j/GDS), fitur, model, explain, GenAI, guardrail, impact |
| `pipelines/run_offline.py` | menjalankan seluruh pipeline offline |
| `app/` | dashboard Streamlit: `Home.py` (login dan navigasi per peran), `views/` (halaman), `components/` |
| `tests/` | tes guardrail, no-lookahead, golden set dan DeepEval |
| `config/settings.yaml` | path, jendela waktu, Neo4j, LLM, akun demo |
| `Dockerfile`, `docker-compose.yml`, `docker/` | menjalankan semuanya dengan Docker |
