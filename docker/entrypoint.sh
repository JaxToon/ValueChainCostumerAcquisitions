#!/bin/sh
# Entrypoint container app.
#   app      : siapkan data bila belum ada, lalu jalankan dashboard (default)
#   pipeline : bangun ulang data (generator + pipeline offline), lalu selesai
#   lainnya  : dijalankan apa adanya, misalnya: docker compose run --rm app python -m pytest tests -q
set -e

has_data() { [ -f data/processed/scores/nbo_test.parquet ] && [ -f outputs/model/ringkasan_model.csv ]; }

wait_neo4j() {
  echo "[rm-copilot] menunggu Neo4j di ${NEO4J_URI} ..."
  python - <<'PY'
import os, time
from neo4j import GraphDatabase
for i in range(90):
    try:
        with GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])) as d:
            d.verify_connectivity()
        print("[rm-copilot] Neo4j siap"); break
    except Exception:
        time.sleep(5)
else:
    raise SystemExit("[rm-copilot] Neo4j tidak bisa dihubungi setelah 7,5 menit")
PY
}

build_data() {
  if [ ! -f synthetic_generator/output/data_bank/nasabah.csv ]; then
    echo "[rm-copilot] 1/2 membuat data sintetis (sekitar 3 menit) ..."
    (cd synthetic_generator && python run.py)
  fi
  wait_neo4j
  echo "[rm-copilot] 2/2 pipeline offline: cleaning, Neo4j, graph, fitur, model, laporan (sekitar 30-60 menit) ..."
  python -m pipelines.run_offline
}

case "$1" in
  app)
    if ! has_data; then
      echo "[rm-copilot] data/processed belum ada: membangun data sekali saja."
      echo "[rm-copilot] Lebih cepat: ekstrak zip data dari tim ke folder data/ dan outputs/, lalu docker compose up lagi."
      build_data
    fi
    exec streamlit run app/Home.py --server.address=0.0.0.0 --server.port=8501
    ;;
  pipeline)
    build_data
    ;;
  *)
    exec "$@"
    ;;
esac
