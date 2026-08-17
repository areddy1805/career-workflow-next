"""SLICE 2/3: batch resolve service — L0..L6 order, safety, batching."""
from __future__ import annotations

from src.copilot.resolve import Field, resolve_batch


def test_email_resolves_from_ground_truth_l1():
    out = resolve_batch(
        [Field(field_id="f1", label="Email Address", kind="email")],
        profile_id="ai",
        mode="SAFE",
        llm=None,
    )
    r = out["resolutions"][0]
    assert r["source"] == "L1_ground_truth"
    assert r["value"] == "abhilashrreddy1991@gmail.com"
    assert r["status"] == "auto"


def test_total_experience_resolves_l3_profile():
    out = resolve_batch(
        [Field(field_id="f2", label="Total years of experience", kind="select")],
        llm=None,
    )
    r = out["resolutions"][0]
    assert r["source"] == "L3_deterministic_profile"
    assert r["value"] == "5"
    assert r["status"] == "auto"


def test_notice_period_strategic_confirm():
    out = resolve_batch(
        [Field(field_id="f3", label="Notice period", kind="select", options=["30 Days", "60 Days"])],
        mode="ASSISTED",
        llm=None,
    )
    r = out["resolutions"][0]
    assert r["source"] == "L3_deterministic_profile"
    assert r["sensitivity"] == "STRATEGIC"
    assert r["status"] == "confirm"


def test_work_authorization_never_llm():
    calls = []

    def llm(_reqs):
        calls.append(1)
        return [{"field_id": "f4", "intent": "legal.work_authorization", "confidence": 0.99, "answerable": True, "requires_review": False, "reason_code": "x"}]

    out = resolve_batch(
        [Field(field_id="f4", label="Are you authorized to work in India?", kind="radio")],
        mode="FULL",
        llm=llm,
    )
    r = out["resolutions"][0]
    assert calls == [], "LLM must never be called for legal fields"
    assert r["source"] == "L6_human_review"
    assert r["status"] == "review"


def test_unknown_question_batched_to_llm_once():
    calls = []

    def llm(reqs):
        calls.append(len(reqs))
        return [
            {"field_id": "q1", "intent": "question.open_ended", "confidence": 0.9, "answerable": True, "requires_review": True, "reason_code": "novel_question"},
            {"field_id": "q2", "intent": "question.why_us", "confidence": 0.85, "answerable": True, "requires_review": True, "reason_code": "novel_question"},
        ]

    out = resolve_batch(
        [
            Field(field_id="q1", label="What factors are influencing your decision to explore opportunities?", kind="textarea"),
            Field(field_id="q2", label="Why do you want to join this company?", kind="textarea"),
        ],
        llm=llm,
    )
    assert calls == [2], "exactly one batched LLM call for two fields"
    assert out["llm_calls"] == 1
    assert all(r["source"] == "L5_semantic_llm" for r in out["resolutions"])
    assert all(r["status"] == "confirm" for r in out["resolutions"])


def test_no_llm_means_human_review_no_fabrication():
    out = resolve_batch(
        [Field(field_id="x1", label="Describe your proudest achievement", kind="textarea")],
        llm=None,
    )
    r = out["resolutions"][0]
    assert r["value"] is None
    assert r["status"] == "review"
    assert r["source"] == "L6_human_review"


def test_answer_memory_l2_reuse():
    import sqlite3

    from src.copilot.answerbank.fingerprint import Question, fingerprint
    from src.copilot.answerbank.store import StoredAnswer, save
    from src.copilot.db.migrate import migrate

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate(conn)
    q = Question(label="Why are you looking for a change?", kind="textarea")
    qfp = fingerprint(q)
    save(
        conn,
        StoredAnswer(
            question_fp=qfp,
            profile_id="ai",
            semantic_answer="Seeking a production GenAI, RAG and agentic AI engineering role.",
            serialized_answer=None,
            status="confirmed",
            canonical_label="employment.reason_for_job_change",
            source="manual",
        ),
    )
    out = resolve_batch(
        [Field(field_id="m1", label="Why are you looking for a change?", kind="textarea")],
        conn=conn,
        llm=None,
    )
    r = out["resolutions"][0]
    assert r["source"] == "L2_answer_memory"
    assert "Seeking a production GenAI" in str(r["value"])


def test_ground_truth_untouched_after_resolve():
    from src.copilot.groundtruth import load_facts

    before = load_facts()["email"].value
    resolve_batch(
        [
            Field(field_id="g1", label="Email Address", kind="email"),
            Field(field_id="g2", label="Notice period", kind="select"),
        ],
        llm=None,
    )
    after = load_facts()["email"].value
    assert before == after == "abhilashrreddy1991@gmail.com"
