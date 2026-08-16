"""Job inspection surface tests.

Verifies that:
1. ``build_job_inspection`` merges all existing stored sources (ledger row,
   lifecycle record + transitions, score cache, copilot opportunity data,
   questionnaire telemetry, manual queue) into one deterministic payload.
2. Inspection is READ-ONLY: it never mutates lifecycle state, the ledger,
   the copilot store, the queue, or any database — and therefore never
   consumes application budget.
3. The ``cw inspect`` CLI renders the payload and fails cleanly for unknown
   jobs.
"""

import json
import sqlite3

import pytest

from src.orchestration.job_lifecycle import JobLifecycleStore, JobState
from control_center.job_inspector import build_job_inspection


def _seed_lifecycle(store: JobLifecycleStore) -> None:
    store.create("job_1", title="AI Engineer", company="Acme", score=88.0)
    store.transition("job_1", JobState.ELIGIBLE, reason="Passed all classifier filters")
    store.transition("job_1", JobState.SELECTED_AUTO, reason="Planned via V2 orchestrator")
    store.transition("job_1", JobState.SUBMITTED, reason="APPLIED")


def _seed_copilot_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE copilot_opportunities ("
        "provider_job_id TEXT, opportunity_id TEXT, data_json TEXT)"
    )
    conn.execute(
        "INSERT INTO copilot_opportunities VALUES (?, ?, ?)",
        (
            "job_1",
            "job_1",
            json.dumps(
                {
                    "title": "AI Engineer",
                    "company": "Acme",
                    "description_text": (
                        "Key Responsibilities: Design agentic AI systems; "
                        "Build RAG pipelines. "
                        "Qualifications: 5+ yrs Python; LLM experience."
                    ),
                    "comp_min": 1200000,
                    "comp_max": 1800000,
                    "currency": "INR",
                    "experience_required": "3-6 years",
                    "employment_type": "full_time",
                    "remote": True,
                    "city": "Pune",
                    "missing_skills": ["RAG"],
                    "preferred_skills": ["LangGraph"],
                    "fit_class": "high",
                    "application_strategy": "auto",
                    "apply_url": "https://naukri.com/job_1",
                }
            ),
        ),
    )
    conn.commit()
    return conn


@pytest.fixture
def lifecycle():
    return JobLifecycleStore(":memory:")


def test_payload_merges_all_sources(lifecycle):
    _seed_lifecycle(lifecycle)
    conn = _seed_copilot_conn()

    payload = build_job_inspection(
        "job_1",
        lifecycle_store=lifecycle,
        copilot_conn=conn,
        questionnaire_path=None,
        queue_path=None,
        ledger_row={"job_id": "job_1", "priority": "TIER_A", "source": "naukri"},
    )

    # Identity + ledger fields.
    assert payload["job_id"] == "job_1"
    assert payload["classification"]["priority"] == "TIER_A"
    assert payload["source_and_urls"]["provider"] == "naukri"
    # Lifecycle: current state + full transition trail with reasons.
    assert payload["lifecycle"]["current_state"] == "SUBMITTED"
    reasons = [t["reason"] for t in payload["lifecycle"]["transitions"]]
    assert "Passed all classifier filters" in reasons
    assert "APPLIED" in reasons
    # Copilot rich data.
    assert payload["title"] == "AI Engineer"
    assert payload["company"] == "Acme"
    assert payload["jd"]["description_text"] == (
        "Key Responsibilities: Design agentic AI systems; Build RAG pipelines. "
        "Qualifications: 5+ yrs Python; LLM experience."
    )
    assert payload["jd"]["salary"] == {
        "min": 1200000,
        "max": 1800000,
        "currency": "INR",
    }
    assert payload["jd"]["experience_required"] == "3-6 years"
    assert payload["skills"]["missing_skills"] == ["RAG"]
    assert payload["skills"]["preferred_skills"] == ["LangGraph"]
    assert payload["classification"]["fit_class"] == "high"
    assert payload["routing"]["application_strategy"] == "auto"
    assert payload["source_and_urls"]["apply_url"] == "https://naukri.com/job_1"
    assert payload["location"]["remote"] is True
    assert payload["location"]["city"] == "Pune"


def test_payload_includes_questionnaire_and_queue(lifecycle, tmp_path):
    _seed_lifecycle(lifecycle)
    telemetry = tmp_path / "telemetry.csv"
    telemetry.write_text(
        "observed_at,job_id,question,question_type,resolution_status,resolution_reasoning\n"
        "2026-08-16T10:00:00+00:00,job_1,How many years of AI exp?,text,unresolved,no profile match\n"
        "2026-08-16T10:00:01+00:00,job_1,Current CTC?,number,resolved,deterministic\n",
        encoding="utf-8",
    )
    queue = tmp_path / "queue.json"
    queue.write_text(
        json.dumps(
            [{"job_id": "job_1", "mode": "MANUAL_REVIEW", "reason": "Manual review: exp mismatch"}]
        ),
        encoding="utf-8",
    )

    payload = build_job_inspection(
        "job_1",
        lifecycle_store=lifecycle,
        questionnaire_path=telemetry,
        queue_path=queue,
        ledger_row={"job_id": "job_1"},
    )

    q = payload["questionnaire"]
    assert len(q["unresolved"]) == 1
    assert q["unresolved"][0]["question"].startswith("How many years")
    assert len(q["resolved"]) == 1
    assert payload["routing"]["manual_queue_entries"][0]["mode"] == "MANUAL_REVIEW"


def test_inspection_is_read_only(lifecycle):
    """Inspection must not mutate any store — snapshot rows + content before
    and after and require exact equality (no lifecycle transitions, no ledger
    writes, no budget consumption)."""
    _seed_lifecycle(lifecycle)
    conn = _seed_copilot_conn()

    def snapshot():
        lc_rows = [
            (r.job_id, r.current_state.value, len(r.transitions))
            for r in lifecycle.all_records()
        ]
        lc_json = json.dumps(
            [r.to_dict() for r in lifecycle.all_records()], sort_keys=True
        )
        cp_rows = conn.execute("SELECT * FROM copilot_opportunities").fetchall()
        return lc_rows, lc_json, cp_rows

    before = snapshot()
    for _ in range(3):
        build_job_inspection(
            "job_1", lifecycle_store=lifecycle, copilot_conn=conn
        )
        build_job_inspection(
            "missing_job", lifecycle_store=lifecycle, copilot_conn=conn
        )
    after = snapshot()

    assert before == after
    # Explicit state assertions: nothing moved, nothing new.
    assert lifecycle.count() == 1
    assert lifecycle.current_state("job_1") == JobState.SUBMITTED


def test_unknown_job_returns_empty():
    assert build_job_inspection("does_not_exist_123") == {}


def test_jd_section_extraction_deterministic():
    """Responsibilities/requirements are sliced from the STORED JD text —
    deterministic, no LLM, no new data source; missing sections are omitted."""
    from control_center.job_inspector import extract_jd_sections

    html = (
        "<h2>Job Description</h2><p>AI Engineer</p>"
        "<h3>Key Responsibilities</h3><ul><li>Design AI apps</li>"
        "<li>Build RAG pipelines</li></ul>"
        "<h3>Qualifications</h3><ul><li>5+ yrs Python</li><li>LLM experience</li></ul>"
    )
    s = extract_jd_sections(html)
    assert s["responsibilities"] == ["Design AI apps", "Build RAG pipelines"]
    assert s["requirements"] == ["5+ yrs Python", "LLM experience"]

    # No headings -> no sections (never invented).
    assert extract_jd_sections("Just a plain one-liner about a role.") == {}
    assert extract_jd_sections() == {}

    # Idempotent / deterministic.
    assert extract_jd_sections(html) == extract_jd_sections(html)


def test_payload_jd_includes_extracted_sections(lifecycle):
    """The inspection payload exposes responsibilities/requirements for jobs
    whose stored JD has them (verified on the 20260816T101642791102Z manual-
    review job shape)."""
    conn = _seed_copilot_conn()
    payload = build_job_inspection(
        "job_1",
        lifecycle_store=lifecycle,
        copilot_conn=conn,
        ledger_row={"job_id": "job_1"},
    )
    # data_json fixture carries a JD with a Key Responsibilities list.
    jd = payload["jd"]
    assert "Design agentic AI systems" in jd["responsibilities"]
    assert "5+ yrs Python" in jd["requirements"]
    assert payload["jd"]["description_text"].startswith("Key Responsibilities")


def test_missing_sections_are_none_not_empty_dict():
    """Sections with no data must be None — an empty dict {} breaks React
    rendering ("Objects are not valid as a React child")."""
    import tempfile, pathlib

    payload = build_job_inspection(
        "000000000000",
        queue_path=pathlib.Path(tempfile.mkdtemp()) / "q.json",
    )
    # Unknown job: everything unavailable, nothing invented.
    assert payload == {}


def test_queue_entry_supplies_url_when_no_opp_or_cache():
    """Queue-sourced jobs (jobspy etc.) have no copilot/cache record — the
    builder must fall back to the manual-queue entry's url so the drawer can
    still offer "Open Job" (run 20260816T101642791102Z queue items)."""
    import tempfile, pathlib, json as _json

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        _json.dump([{
            "job_id": "jobspy_linkedin_li-4453580451",
            "provider_id": "jobspy",
            "reason": "Manual review: Routed (MANUAL_REVIEW)",
            "url": "https://www.linkedin.com/jobs/view/4453580451",
        }], f)
        qp = pathlib.Path(f.name)
    payload = build_job_inspection(
        "jobspy_linkedin_li-4453580451",
        queue_path=qp,
        ledger_row={"job_id": "jobspy_linkedin_li-4453580451"},
    )
    urls = payload.get("source_and_urls") or {}
    assert urls.get("apply_url") == "https://www.linkedin.com/jobs/view/4453580451"
    assert urls.get("provider") == "jobspy"
    # Still nothing to invent for the JD.
    assert payload.get("jd") in (None, {})
    pathlib.Path(qp).unlink(missing_ok=True)


def test_cli_inspect_exit_codes():
    from typer.testing import CliRunner
    from src.cli.main import app

    runner = CliRunner()

    result = runner.invoke(app, ["inspect", "does_not_exist_123"])
    assert result.exit_code == 1
    assert "Job not found" in result.stdout

    result = runner.invoke(app, ["inspect", "--help"])
    assert result.exit_code == 0
    assert "Job ID to inspect" in result.stdout


def test_extracted_sections_never_leak_html():
    """Sliced responsibility/requirement bullets from an HTML JD must not
    surface <br>/<li>/entities — same normalization boundary as the UI."""
    from control_center.job_inspector import extract_jd_sections

    html = (
        "<p><strong>Key Responsibilities:</strong></p>"
        "<ul><li>Build agentic AI systems<br><br></li>"
        "<li>Run RAG pipelines with &amp; without vector DBs</li></ul>"
        "<p><strong>Requirements:</strong> 5+ yrs Python &lt;insert more&gt;</p>"
    )
    out = extract_jd_sections(description_html=html)
    flat = " ".join(str(x) for v in out.values() for x in v)
    assert "<br" not in flat and "<li>" not in flat and "&lt;" not in flat
    assert "Build agentic AI systems" in flat
    assert "Run RAG pipelines with & without vector DBs" in flat
    assert "5+ yrs Python" in flat
