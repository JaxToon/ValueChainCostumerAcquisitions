"""Guardrail layer 4 (monitoring and audit): every request, tool call, guardrail result,
output and RM decision is written to SQLite (outputs/audit.sqlite). IDs are stored masked."""
import hashlib
import json
import sqlite3
from datetime import datetime

from src.config import path, settings

SCHEMA = """CREATE TABLE IF NOT EXISTS log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, waktu TEXT, pengguna TEXT, halaman TEXT, entitas TEXT,
  input TEXT, guardrail_input TEXT, tool_calls TEXT, output TEXT, guardrail_output TEXT,
  status TEXT, keputusan_rm TEXT, catatan TEXT, model TEXT, versi_prompt TEXT)"""


def _db():
    con = sqlite3.connect(path("outputs") / "audit.sqlite")
    con.execute(SCHEMA)
    have = {r[1] for r in con.execute("PRAGMA table_info(log)")}
    for col in ("model", "versi_prompt"):   # logs created before these columns existed
        if col not in have:
            con.execute(f"ALTER TABLE log ADD COLUMN {col} TEXT")
    return con


def prompt_version() -> str:
    """Short hash of every prompt the generator sees, so each logged answer traces to its prompt."""
    from src.genai import llm, prompts
    text = prompts.SYSTEM + prompts.AGENT + prompts.FINAL_STEP + llm.GUARD_PROMPT
    return hashlib.sha256(text.encode()).hexdigest()[:10]


def mask_id(entity: str) -> str:
    return entity[:2] + "****" + entity[-2:] if entity and len(entity) > 4 else "****"


def write(halaman: str, entitas: str, input_text: str, guardrail_input: dict, tool_calls: list, output: dict,
          guardrail_output: dict, status: str, pengguna: str = "RM-demo") -> int:
    with _db() as con:
        cur = con.execute(
            "INSERT INTO log (waktu, pengguna, halaman, entitas, input, guardrail_input, tool_calls, output, guardrail_output, status,"
            " model, versi_prompt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), pengguna, halaman, mask_id(entitas), input_text,
             json.dumps(guardrail_input, ensure_ascii=False), json.dumps(tool_calls, ensure_ascii=False, default=str),
             json.dumps(output, ensure_ascii=False, default=str), json.dumps(guardrail_output, ensure_ascii=False, default=str), status,
             f"{settings()['llm']['provider']}:{settings()['llm']['model_generator']}", prompt_version()))
        return cur.lastrowid


def decide(log_id: int, keputusan: str, catatan: str = ""):
    """RM decision: Setujui, Edit, or Tolak (human in the loop)."""
    with _db() as con:
        con.execute("UPDATE log SET keputusan_rm = ?, catatan = ? WHERE id = ?", (keputusan, catatan, log_id))


def read(limit: int = 500):
    import pandas as pd
    with _db() as con:
        return pd.read_sql(f"SELECT * FROM log ORDER BY id DESC LIMIT {int(limit)}", con)
