"""Red team for the Tanya AI input guardrail (tests/golden/red_team.py).
Rules layer: must refuse every known attack and pass every legitimate question.
Full stack (rules + local Gemma classifier): must also refuse unseen paraphrases; skipped when
Ollama is not running."""
import pytest

from src.genai import llm, tanya
from src.guardrails import input_guard
from tests.golden.red_team import ATTACKS, LEGIT, UNSEEN


def _ollama_up() -> bool:
    return llm.guard_label("Apa itu Tabungan Plus?") is not None


@pytest.mark.parametrize("kind,text", ATTACKS)
def test_aturan_menolak_serangan(kind, text):
    assert not input_guard.check(text).allowed


@pytest.mark.parametrize("text", LEGIT)
def test_aturan_tidak_salah_blokir(text):
    assert input_guard.check(text).allowed


@pytest.mark.skipif(not _ollama_up(), reason="Ollama/Gemma tidak berjalan")
@pytest.mark.parametrize("kind,text", UNSEEN)
def test_lapisan_semantik_menolak_serangan_baru(kind, text):
    assert tanya.answer(text)["diblokir"] is True
