"""Unit tests for CP-3-05: profile switching service."""

import pytest

from src.copilot.answerbank.profiles import (
    PROFILE_RESUME_TYPES,
    ProfileContext,
    switch_profile,
)
from src.copilot.answerbank.store import StoredAnswer, list_answers, save
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


def answer(profile_id: str, semantic_answer: str) -> StoredAnswer:
    return StoredAnswer(
        question_fp="fp-rag-years",
        profile_id=profile_id,
        semantic_answer=semantic_answer,
        serialized_answer=semantic_answer,
        source=AnswerSource.MANUAL.value,
        status=AnswerStatus.CONFIRMED.value,
    )


# ------------------------------------------------------------- switching


def test_known_profiles_map_to_resume_types():
    assert switch_profile("ai").resume_type == "AI"
    assert switch_profile("fde").resume_type == "FDE"
    assert switch_profile("generic").resume_type == "generic"


def test_mapping_matches_resume_router_family():
    # 06 §5: profiles = AI, FDE, generic (matches ResumeRouter)
    assert set(PROFILE_RESUME_TYPES) == {"ai", "fde", "generic"}


def test_unknown_profile_is_free_form_namespace():
    ctx = switch_profile("contractor")
    assert ctx.profile_id == "contractor"
    assert ctx.resume_type == "contractor"


def test_case_insensitive_known_mapping():
    assert switch_profile("AI").resume_type == "AI"
    assert switch_profile("FDE").resume_type == "FDE"


def test_context_round_trip():
    ctx = switch_profile("ai")
    assert ctx.to_dict() == {"profile_id": "ai", "resume_type": "AI"}
    assert ProfileContext("ai", "AI") == ctx


# --------------------------------------------------------- no cross-leak


def test_switch_does_not_mutate_answer_rows(fresh_db):
    save(fresh_db, answer("ai", "5 years"))
    save(fresh_db, answer("fde", "8 years"))
    before = [a.to_dict() for a in list_answers(fresh_db)]

    ctx = switch_profile("fde")
    assert ctx.profile_id == "fde"

    after = [a.to_dict() for a in list_answers(fresh_db)]
    assert after == before  # atomic: nothing moved, copied, or rewritten


def test_no_cross_profile_leakage(fresh_db):
    """06 §5 AC: after a switch, the old namespace is invisible and intact."""
    save(fresh_db, answer("ai", "5 years"))
    switch_profile("fde")

    fde_answers = list_answers(fresh_db, profile_id="fde")
    assert fde_answers == []  # nothing leaked into the new namespace

    ai_answers = list_answers(fresh_db, profile_id="ai")
    assert len(ai_answers) == 1  # old namespace untouched
    assert ai_answers[0].semantic_answer == "5 years"
