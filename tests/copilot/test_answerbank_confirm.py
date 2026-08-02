"""Unit + integration tests for CP-3-04: confirmation workflow + override."""

import pytest

from src.copilot.answerbank.confirm import confirm, set_locked
from src.copilot.answerbank.fingerprint import Question, fingerprint
from src.copilot.answerbank.resolver import (
    ResolveContext,
    resolve,
)
from src.copilot.answerbank.store import StoredAnswer, get, save
from src.copilot.constants import AnswerSource, AnswerStatus
from src.copilot.db.db import open_copilot_db
from src.copilot.exceptions import CopilotError


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 't' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def store_answer(fresh_db, **overrides) -> StoredAnswer:
    defaults = dict(
        question_fp="fp-years",
        profile_id="ai",
        semantic_answer="3 years",
        serialized_answer="3 years",
        source=AnswerSource.DETERMINISTIC.value,
        status=AnswerStatus.AUTO.value,
        confidence=1.0,
    )
    defaults.update(overrides)
    return save(fresh_db, StoredAnswer(**defaults))


# --------------------------------------------------------------- confirm


def test_confirm_creates_human_answer(fresh_db):
    stored = confirm(fresh_db, "fp-new", "ai", "5 years", actor="ada")
    assert stored.source == AnswerSource.MANUAL.value
    assert stored.status == AnswerStatus.CONFIRMED.value
    assert stored.semantic_answer == "5 years"
    assert stored.confidence == 1.0
    assert stored.reason == "confirmed by ada"

    loaded = get(fresh_db, "fp-new", "ai")
    assert loaded.semantic_answer == "5 years"
    assert loaded.source == AnswerSource.MANUAL.value


def test_confirm_overrides_generated_answer(fresh_db):
    """Override wins (CP-3-04 AC): confirmable/generated rows are replaced."""
    store_answer(fresh_db, status=AnswerStatus.CONFIRM.value,
                 source=AnswerSource.LLM.value)
    stored = confirm(fresh_db, "fp-years", "ai", "7 years")
    assert stored.semantic_answer == "7 years"
    assert stored.source == AnswerSource.MANUAL.value
    assert stored.status == AnswerStatus.CONFIRMED.value


def test_confirm_overrides_confirmed_answer(fresh_db):
    store_answer(fresh_db, status=AnswerStatus.CONFIRMED.value,
                 source=AnswerSource.MANUAL.value)
    stored = confirm(fresh_db, "fp-years", "ai", "9 years")
    assert stored.semantic_answer == "9 years"
    assert stored.status == AnswerStatus.CONFIRMED.value


def test_confirm_rejected_while_locked(fresh_db):
    store_answer(fresh_db, status=AnswerStatus.LOCKED.value)
    with pytest.raises(CopilotError, match="unlock before confirming"):
        confirm(fresh_db, "fp-years", "ai", "7 years")
    # lock survived
    assert get(fresh_db, "fp-years", "ai").semantic_answer == "3 years"


def test_confirm_after_unlock_works(fresh_db):
    store_answer(fresh_db, status=AnswerStatus.LOCKED.value)
    set_locked(fresh_db, "fp-years", "ai", False)  # unlock → confirmed
    stored = confirm(fresh_db, "fp-years", "ai", "7 years")
    assert stored.semantic_answer == "7 years"
    assert stored.status == AnswerStatus.CONFIRMED.value


def test_confirm_preserves_canonical_metadata(fresh_db):
    store_answer(fresh_db, canonical_label="experience.rag_years",
                 category="experience")
    stored = confirm(fresh_db, "fp-years", "ai", "4 years")
    assert stored.canonical_label == "experience.rag_years"
    assert stored.category == "experience"


# ----------------------------------------------------------------- lock


def test_set_locked_pins_answer(fresh_db):
    store_answer(fresh_db)
    stored = set_locked(fresh_db, "fp-years", "ai", True)
    assert stored.status == AnswerStatus.LOCKED.value
    assert stored.semantic_answer == "3 years"  # values untouched
    assert get(fresh_db, "fp-years", "ai").status == AnswerStatus.LOCKED.value


def test_set_locked_idempotent_when_already_locked(fresh_db):
    store_answer(fresh_db, status=AnswerStatus.LOCKED.value)
    stored = set_locked(fresh_db, "fp-years", "ai", True)
    assert stored.status == AnswerStatus.LOCKED.value


def test_set_locked_unlock_returns_to_confirmed(fresh_db):
    store_answer(fresh_db, status=AnswerStatus.LOCKED.value)
    stored = set_locked(fresh_db, "fp-years", "ai", False)
    assert stored.status == AnswerStatus.CONFIRMED.value


def test_set_locked_missing_answer_raises(fresh_db):
    with pytest.raises(CopilotError, match="no stored answer to lock"):
        set_locked(fresh_db, "fp-ghost", "ai", True)


def test_set_locked_unlock_not_locked_raises(fresh_db):
    store_answer(fresh_db)
    with pytest.raises(CopilotError, match="not locked"):
        set_locked(fresh_db, "fp-years", "ai", False)


def test_set_locked_superseded_raises(fresh_db):
    store_answer(fresh_db, status=AnswerStatus.SUPERSEDED.value)
    with pytest.raises(CopilotError, match="superseded"):
        set_locked(fresh_db, "fp-years", "ai", True)


# ------------------------------------------------- resolver integration


def test_resolver_serves_confirmed_human_answer(fresh_db):
    question = Question(label="How many years of experience?")
    qf = fingerprint(question)
    confirm(fresh_db, qf, "ai", "6 years")
    resolution = resolve(
        fresh_db, question, "ai",
        ResolveContext(conn=fresh_db, profile={}, hybrid_resolver=lambda q, p: {
            "status": "resolved", "source": "llm", "semantic_answer": "wrong",
            "serialized_answer": "wrong", "confidence": 0.9, "reasoning": "x",
        }, cache={}),
    )
    assert resolution.source == AnswerSource.MANUAL.value
    assert resolution.semantic_answer == "6 years"
    assert resolution.status == AnswerStatus.CONFIRMED.value  # D-013 passthrough


def test_resolver_serves_locked_answer(fresh_db):
    question = Question(label="What is your notice period?")
    qf = fingerprint(question)
    confirm(fresh_db, qf, "ai", "30 days")
    set_locked(fresh_db, qf, "ai", True)
    resolution = resolve(
        fresh_db, question, "ai",
        ResolveContext(conn=fresh_db, profile={}, hybrid_resolver=lambda q, p: {
            "status": "resolved", "source": "llm", "semantic_answer": "wrong",
            "serialized_answer": "wrong", "confidence": 0.9, "reasoning": "x",
        }, cache={}),
    )
    assert resolution.source == AnswerSource.MANUAL.value
    assert resolution.semantic_answer == "30 days"
    assert resolution.status == AnswerStatus.LOCKED.value
