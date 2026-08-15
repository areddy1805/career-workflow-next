"""Tests for CP-3-02: resolution engine wrapper + cache (06 §3 order)."""

import pytest

from src.copilot.answerbank.fingerprint import Question, fingerprint
from src.copilot.answerbank.resolver import (
    AnswerResolution,
    ResolveContext,
    resolve,
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


def make_question(**overrides):
    defaults = dict(label="Years of Python experience?")
    defaults.update(overrides)
    return Question(**defaults)


def resolved_hybrid(**overrides):
    result = {
        "status": "resolved",
        "source": "deterministic",
        "semantic_answer": "5",
        "serialized_answer": "5",
        "confidence": 1.0,
        "reasoning": "test",
    }
    result.update(overrides)
    return result


def store_answer(conn, question, profile_id="ai", **overrides):
    row = {
        "question_fp": fingerprint(question),
        "profile_id": profile_id,
        "source": "manual",
        "semantic_answer": "stored-answer",
        "serialized_answer": "stored-answer",
        "confidence": 1.0,
        "status": "confirmed",
        "reason": "human",
    }
    row.update(overrides)
    conn.execute(
        "INSERT INTO copilot_answers (question_fp, profile_id, source, "
        "semantic_answer, serialized_answer, confidence, status, reason) "
        "VALUES (:question_fp, :profile_id, :source, :semantic_answer, "
        ":serialized_answer, :confidence, :status, :reason)",
        row,
    )
    conn.commit()


def test_resolution_round_trip():
    resolution = AnswerResolution(
        question_fp="aabbccdd",
        source=AnswerSource.LLM.value,
        semantic_answer="5 years",
        serialized_answer="5",
        confidence=0.9,
        status=AnswerStatus.CONFIRM.value,
        reasoning="generated",
    )
    restored = AnswerResolution.from_dict(resolution.to_dict())
    assert restored == resolution


# ------------------------------------------------------- order: stored first


def test_stored_answer_wins(fresh_db):
    question = make_question()
    store_answer(fresh_db, question)
    resolution = resolve(fresh_db, question, "ai")
    assert resolution.source == "manual"
    assert resolution.semantic_answer == "stored-answer"
    assert resolution.status == "confirmed"


def test_stored_is_profile_namespaced(fresh_db):
    question = make_question()
    store_answer(fresh_db, question, profile_id="ai")

    def fake_engine(pipeline_question, profile):
        return resolved_hybrid(
            source="deterministic", semantic_answer="3",
            serialized_answer="3",
        )

    other = resolve(
        fresh_db, question, "fde",
        ResolveContext(
            conn=fresh_db, profile={}, hybrid_resolver=fake_engine, cache={}
        ),
    )
    # no stored answer for the fde namespace → falls through to deterministic
    assert other.source == AnswerSource.DETERMINISTIC.value


def test_superseded_stored_is_skipped(fresh_db):
    question = make_question()
    store_answer(fresh_db, question, status="superseded")

    def fake_engine(pipeline_question, profile):
        return resolved_hybrid(
            source="deterministic", semantic_answer="3",
            serialized_answer="3",
        )

    resolution = resolve(
        fresh_db, question, "ai",
        ResolveContext(
            conn=fresh_db, profile={}, hybrid_resolver=fake_engine, cache={}
        ),
    )
    assert resolution.source == AnswerSource.DETERMINISTIC.value


# --------------------------------------------------- order: deterministic


def test_deterministic_resolution(fresh_db):
    """Integration: real pipeline deterministic layer resolves + serializes."""
    from config.candidate_profile import CANDIDATE_PROFILE

    question = make_question(label="Years of experience?")
    resolution = resolve(
        fresh_db, question, "ai",
        ResolveContext(conn=fresh_db, profile=CANDIDATE_PROFILE),
    )
    assert resolution.source == AnswerSource.DETERMINISTIC.value
    assert resolution.status == AnswerStatus.AUTO.value
    assert resolution.confidence == 1.0
    assert resolution.question_fp == fingerprint(question)
    assert resolution.semantic_answer is not None


def test_deterministic_serializes_select_via_kind(fresh_db):
    """kind select maps to list-menu serialization (pipeline questionType)."""
    from config.candidate_profile import CANDIDATE_PROFILE

    question = make_question(
        label="How many years of experience do you have?",
        kind="select",
        options=["0-2 years", "3-5 years", "6+ years"],
    )
    resolution = resolve(
        fresh_db, question, "ai",
        ResolveContext(conn=fresh_db, profile=CANDIDATE_PROFILE),
    )
    assert resolution.source == AnswerSource.DETERMINISTIC.value
    assert resolution.status == AnswerStatus.AUTO.value
    assert resolution.serialized_answer is not None


# ------------------------------------------------- order: generated LLM + cache


def test_llm_generated_is_cached_by_fp_and_profile(fresh_db):
    question = make_question(label="Describe your approach to debugging")
    calls = []

    def fake_engine(pipeline_question, profile):
        calls.append(pipeline_question)
        return resolved_hybrid(
            source="llm", semantic_answer="Triage then bisect",
            serialized_answer="Triage then bisect", confidence=0.9,
        )

    context = ResolveContext(
        conn=fresh_db, profile={}, hybrid_resolver=fake_engine, cache={}
    )
    first = resolve(fresh_db, question, "ai", context)
    second = resolve(fresh_db, question, "ai", context)
    assert first.source == AnswerSource.LLM.value
    assert first.status == AnswerStatus.CONFIRM.value
    assert first is second  # cache hit returns the same object
    assert len(calls) == 1  # engine invoked exactly once


def test_llm_cache_is_profile_scoped(fresh_db):
    question = make_question(label="Describe your approach to debugging")
    calls = []

    def fake_engine(pipeline_question, profile):
        calls.append(pipeline_question)
        return resolved_hybrid(
            source="llm", semantic_answer="x", serialized_answer="x",
            confidence=0.9,
        )

    context = ResolveContext(
        conn=fresh_db, profile={}, hybrid_resolver=fake_engine, cache={}
    )
    resolve(fresh_db, question, "ai", context)
    resolve(fresh_db, question, "fde", context)
    assert len(calls) == 2  # different profile → separate cache slot


def test_llm_high_confidence_is_auto(fresh_db):
    question = make_question(label="Describe your approach to debugging")

    def fake_engine(pipeline_question, profile):
        return resolved_hybrid(
            source="llm", semantic_answer="x", serialized_answer="x",
            confidence=0.97,
        )

    resolution = resolve(
        fresh_db, question, "ai",
        ResolveContext(
            conn=fresh_db, profile={}, hybrid_resolver=fake_engine, cache={}
        ),
    )
    assert resolution.status == AnswerStatus.AUTO.value


# ------------------------------------------------- order: manual review


def test_manual_review_surfaces_confirm(fresh_db):
    question = make_question(label="PAN number")

    def fake_engine(pipeline_question, profile):
        return {
            "status": "manual_review",
            "source": "llm_safety_gate",
            "semantic_answer": None,
            "serialized_answer": None,
            "confidence": 0.3,
            "reasoning": "Sensitive data — abstain.",
        }

    resolution = resolve(
        fresh_db, question, "ai",
        ResolveContext(conn=fresh_db, profile={}, hybrid_resolver=fake_engine),
    )
    assert resolution.status == AnswerStatus.CONFIRM.value
    assert resolution.source == AnswerSource.LLM.value
    assert resolution.confidence == 0.3
    assert "abstain" in (resolution.reasoning or "")


def test_deterministic_failure_short_circuits_confirm(fresh_db, monkeypatch):
    """A rejected deterministic value never falls through to the LLM."""
    question = make_question(label="Something the rules reject")
    monkeypatch.setattr(
        "src.copilot.answerbank.resolver._deterministic",
        lambda q, p: {
            "status": "manual_review",
            "source": "deterministic_constraint_failure",
            "semantic_answer": "v",
            "serialized_answer": None,
            "confidence": 1.0,
            "reasoning": "constraint rejection",
        },
    )
    resolution = resolve(
        fresh_db, question, "ai", ResolveContext(conn=fresh_db, cache={})
    )
    assert resolution.status == AnswerStatus.CONFIRM.value
    assert resolution.source == AnswerSource.DETERMINISTIC.value
    assert resolution.semantic_answer == "v"
