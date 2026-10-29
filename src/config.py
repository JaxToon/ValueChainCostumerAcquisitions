"""Paths, settings and secrets for the offline pipeline (config/settings.yaml, .env)."""
import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


@lru_cache
def settings() -> dict:
    return yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))


def path(key: str) -> Path:
    p = ROOT / settings()["paths"][key]
    if key in ("processed", "outputs"):
        p.mkdir(parents=True, exist_ok=True)
    return p


# Values a container may pass as environment variables (Docker); they override .env.
ENV_KEYS = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "OPENAI_API_KEY", "OLLAMA_BASE_URL")


def env() -> dict:
    values = dict(dotenv_values(ROOT / ".env"))
    values.update({k: os.environ[k] for k in ENV_KEYS if os.environ.get(k)})
    return values
