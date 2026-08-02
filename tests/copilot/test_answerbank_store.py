"""Unit + integration tests for CP-3-03: answer store CRUD + profiles."""

import pytest

from src.copilot.answerbank.fingerprint import Question, fingerprint
from src.copilot.answerbank.resolver import (
    ResolveContext,
    resolve,
)
from src.copilot.answerbank.store import (
    StoredAnswer,
    get,
    list_answers,
    save,
    supersede,
)
from src.copilot.constants import AnswerSource, AnswerStatus
from src.copilot.db.db import open_copilot_db


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f"copilot:\n  db_path: \"{tmp_path / 't' / 'copilot.db'}\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def answer(**overrides) -> StoredAnswer:
    defaults = dict(
        question_fp="fp-rag-years",
        profile_id="ai",
        semantic_answer="5 years",
        serialized_answer="5 years",
        source=AnswerSource.MANUAL.value,
        status=AnswerStatus.CONFIRMED.value,
        confidence=1.0,
        canonical_label="experience.rag_years",
        category="experience",
    )
    defaults.update(overrides)
    return StoredAnswer(**defaults)


# ------------------------------------------------------------ round-trip


def test_save_and_get_round_trip(fresh_db):
    saved = save(fresh_db, answer())
    assert saved.question_fp == "fp-rag-years"

    loaded = get(fresh_db, "fp-rag-years", "ai")
    assert loaded is not None
    assert loaded.semantic_answer == "5 years"
    assert loaded.serialized_answer == "5 years"
    assert loaded.source == AnswerSource.MANUAL.value
    assert loaded.status == AnswerStatus.CONFIRMED.value
    assert loaded.confidence == 1.0
    assert loaded.canonical_label == "experience.rag_years"
    assert loaded.category == "experience"
    assert loaded.use_count == 0


def test_get_missing_returns_none(fresh_db):
    assert get(fresh_db, "fp-nope", "ai") is None


def test_save_upserts_on_conflict(fresh_db):
    save(fresh_db, answer())
    save(
        fresh_db,
        answer(semantic_answer="6 years", status=AnswerStatus.LOCKED.value),
    )
    loaded = get(fresh_db, "fp-rag-years", "ai")
    assert loaded.semantic_answer == "6 years"
    assert loaded.status == AnswerStatus.LOCKED.value
    # single row per (fp, profile) namespace
    assert len(list_answers(fresh_db)) == 1


# --------------------------------------------------- namespace isolation


def test_profiles_are_isolated_namespaces(fresh_db):
    save(fresh_db, answer(profile_id="ai", semantic_answer="5 years"))
    save(fresh_db, answer(profile_id="fde", semantic_answer="8 years"))
    save(fresh_db, answer(profile_id="generic", semantic_answer="3 years"))

    assert get(fresh_db, "fp-rag-years", "ai").semantic_answer == "5 years"
    assert get(fresh_db, "fp-rag-years", "fde").semantic_answer == "8 years"
    assert get(fresh_db, "fp-rag-years", "generic").semantic_answer == "3 years"

    assert len(list_answers(fresh_db, profile_id="ai")) == 1
    assert len(list_answers(fresh_db, profile_id="fde")) == 1
    assert len(list_answers(fresh_db, profile_id="generic")) == 1
    assert len(list_answers(fresh_db)) == 3


def test_list_filters_status_and_query(fresh_db):
    save(fresh_db, answer(question_fp="fp-a", canonical_label="identity.name",
                          category="identity", semantic_answer="Ada"))
    save(fresh_db, answer(question_fp="fp-b", canonical_label="experience.rag_years",
                          category="experience", semantic_answer="5 years"))
    save(fresh_db, answer(question_fp="fp-c", canonical_label="preference.remote",
                          category="preference", semantic_answer="yes",
                          status=AnswerStatus.LOCKED.value))

    assert len(list_answers(fresh_db, status=AnswerStatus.CONFIRMED.value)) == 2
    assert len(list_answers(fresh_db, status=AnswerStatus.LOCKED.value)) == 1
    assert len(list_answers(fresh_db, query="rag_years")) == 1
    assert len(list_answers(fresh_db, query="Ada")) == 1
    assert len(list_answers(fresh_db, query="experience")) == 1
    # limit/offset
    assert len(list_answers(fresh_db, limit=2)) == 2
    assert len(list_answers(fresh_db, limit=2, offset=2)) == 1


# --------------------------------------------------------------- supersede


def test_supersede_tombstones_row(fresh_db):
    save(fresh_db, answer())
    assert supersede(fresh_db, "fp-rag-years", "ai") is True
    loaded = get(fresh_db, "fp-rag-years", "ai")
    assert loaded.status == AnswerStatus.SUPERSEDED.value
    assert supersede(fresh_db, "fp-ghost", "ai") is False


def test_superseded_answer_is_skipped_by_resolver(fresh_db):
    """06 §3 step 1: stored lookup skips superseded rows — resolution falls
    through to the next layer instead of returning the tombstone."""
    question = Question(label="How many years of RAG experience do you have?")
    save(fresh_db, answer(question_fp=fingerprint(question)))
    supersede(fresh_db, fingerprint(question), "ai")

    def fake_engine(pipeline_question, profile):
        return {
            "status": "resolved",
            "source": "deterministic",
            "semantic_answer": "4 years",
            "serialized_answer": "4 years",
            "confidence": 1.0,
            "reasoning": "canned",
        }

    resolution = resolve(
        fresh_db,
        question,
        "ai",
        ResolveContext(conn=fresh_db, profile={}, hybrid_resolver=fake_engine,
                       cache={}),
    )
    # the tombstone (5 years / manual) is skipped; resolution falls through
    assert resolution.source == AnswerSource.DETERMINISTIC.value
    assert resolution.status == AnswerStatus.AUTO.value
    assert resolution.semantic_answer != "5 years"


def test_stored_answer_to_dict_from_row(fresh_db):
    stored = answer()
    save(fresh_db, stored)
    data = get(fresh_db, "fp-rag-years", "ai").to_dict()
    assert data["question_fp"] == "fp-rag-years"
    assert data["semantic_answer"] == "5 years"
    assert data["canonical_label"] == "experience.rag_years"
