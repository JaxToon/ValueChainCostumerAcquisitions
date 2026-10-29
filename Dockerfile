# RM Copilot Bank: dashboard Streamlit + pipeline offline dalam satu image.
# Dipakai oleh docker-compose.yml (service "app"); data dan hasil di-mount dari host.
FROM python:3.11.17-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libgomp1: dibutuhkan LightGBM dan XGBoost; curl: healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# xgboost-cpu = modul xgboost yang sama tanpa library CUDA (hemat sekitar 480 MB unduhan);
# XGBoost di proyek ini hanya dilatih di CPU.
RUN grep -v '^xgboost==' requirements.txt > /tmp/requirements-docker.txt \
    && pip install -r /tmp/requirements-docker.txt xgboost-cpu==3.2.0

COPY . .
RUN chmod +x docker/entrypoint.sh

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -fs http://localhost:8501/_stcore/health || exit 1
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["app"]
