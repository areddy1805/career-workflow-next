"""Job inspection — read-only, deterministic decision-support payload.

Merges every EXISTING stored data source for one job into a single
inspectable payload so a human can understand what the role actually is,
why the pipeline ranked/selected/rejected it, and whether to apply.

Guarantees
----------
- READ-ONLY: no writes to any store, no lifecycle transitions, no ledger
  records, no queue enqueues, no application-budget consumption.
- ZERO inference: no LLM calls, no provider fetches, no cache writes —
  only data already on disk / in SQLite.
- Deterministic: same job_id -> same payload (modulo appended telemetry).

Sources merged (all pre-existing)
---------------------------------
- application ledger row + status events  (control_center.data)
- JobLifecycleStore record + transitions  (data/job_lifecycle.db)
- job search cache (full JD, salary, tags) + score cache (ai_score/reason)
- copilot opportunity store (rich data_json: JD, comp, skills, fit_class,
  application_strategy, URLs)                (data/copilot.db)
- questionnaire telemetry CSV (resolved/unresolved questions)
- manual action queue (outstanding human tasks for the job)

The CLI (``cw inspect <job_id>``) and the API (GET /api/jobs/{job_id})
share this builder so the two surfaces never diverge.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Source loaders (each returns data for one job; None/missing tolerated)
# ---------------------------------------------------------------------------


def _ledger_row(job_id: str) -> dict[str, Any]:
    from control_center.data import read_applications

    df = read_applications()
    if df.empty or "job_id" not in df.columns:
        return {}
    rows = df[df["job_id"] == job_id]
    if rows.empty:
        return {}
    return {str(k): v for k, v in rows.iloc[0].to_dict().items() if not _is_nan(v)}


def _is_nan(value: Any) -> bool:
    try:
        import math

        return isinstance(value, float) and math.isnan(value)
    except TypeError:
        return False


def _application_events(job_id: str) -> list[dict[str, Any]]:
    from control_center.data import read_application_events

    try:
        df = read_application_events(job_id)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    return [
        {str(k): (None if _is_nan(v) else v) for k, v in row.to_dict().items()}
        for _, row in df.iterrows()
    ]


def _lifecycle_record(job_id: str, store: Any = None) -> dict[str, Any]:
    if store is None:
        from src.orchestration.job_lifecycle import JobLifecycleStore

        db_path = os.getenv(
            "JOB_LIFECYCLE_DB_PATH",
            str(REPO_ROOT / "data" / "job_lifecycle.db"),
        )
        store = JobLifecycleStore(db_path)
    record = store.get(job_id)
    return record.to_dict() if record is not None else {}


def _search_and_score_cache(job_id: str) -> dict[str, Any]:
    """Merge the job search cache entry (full JD etc.) with the score cache
    entry (ai_score/ai_reason) for this job id."""
    from control_center.data import get_job_cache_dict

    try:
        cache = get_job_cache_dict()
    except Exception:
        return {}
    return cache.get(str(job_id), {})


def _copilot_opportunity(job_id: str, conn: Any = None) -> dict[str, Any]:
    """Rich opportunity data (JD text/html, compensation, skills, fit_class,
    application_strategy, URLs).  Matches pipeline-synced rows by
    opportunity_id == job_id; falls back to provider_job_id / fingerprint."""
    if conn is None:
        from src.copilot.db.db import open_copilot_db

        conn = open_copilot_db()
    # Raw data_json match first (works with any schema carrying these
    # columns, incl. minimal test fixtures).
    try:
        rows = conn.execute(
            "SELECT data_json FROM copilot_opportunities "
            "WHERE provider_job_id = ? OR opportunity_id = ? LIMIT 1",
            (str(job_id), str(job_id)),
        ).fetchall()
        if rows:
            import json as _json

            raw = rows[0][0]
            return _json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        pass
    # Fall back to the canonical oppstore accessor.
    try:
        from src.copilot.oppstore import store as oppstore

        opp = oppstore.get(conn, str(job_id))
        if opp is not None:
            return opp.to_dict() if hasattr(opp, "to_dict") else vars(opp)
    except Exception:
        pass
    return {}


def _questionnaire_rows(job_id: str, path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Rows from data/questionnaire_telemetry.csv for this job (resolved and
    unresolved questions observed during application attempts)."""
    path = path or Path(
        os.getenv("QUESTIONNAIRE_TELEMETRY_PATH", str(REPO_ROOT / "data" / "questionnaire_telemetry.csv"))
    )
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("job_id") == str(job_id):
                    rows.append(dict(row))
    except (OSError, csv.Error):
        return []
    return rows


def _manual_queue_entries(job_id: str, path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Outstanding manual-action queue entries for this job (the human task
    list produced by MANUAL_REVIEW / EXTERNAL routing)."""
    path = path or Path(
        os.getenv(
            "MANUAL_ACTION_QUEUE_PATH",
            str(REPO_ROOT / "data" / "manual_action_queue.json"),
        )
    )
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload if isinstance(payload, list) else payload.get("items", [])
    return [
        {str(k): v for k, v in item.items()}
        for item in items
        if str(item.get("job_id", "")) == str(job_id)
    ]


# ---------------------------------------------------------------------------
# Deterministic JD section extraction (responsibilities / requirements)
# ---------------------------------------------------------------------------
# Slices the STORED raw JD (description_html or description_text) at common
# English headings and collects the following bullet items.  No LLM, no new
# data source — purely a presentation projection of what the JD already says.
# Sections that cannot be located are simply omitted (never invented).

import re as _re

_RESPONSIBILITY_HEADINGS = (
    r"key responsibilities",
    r"roles? and responsibilities",
    r"responsibilities",
    r"what you['’`]?ll do",
    r"what you['’`]?ll be doing",
    r"what you will do",
    r"your role",
    r"duties",
)

_REQUIREMENT_HEADINGS = (
    r"qualifications?",
    r"requirements?",
    r"what we['’`]?re looking for",
    r"what we are looking for",
    r"we are looking for",
    r"must have",
    r"good to have",
    r"required skills",
    r"skills required",
    r"experience required",
    r"education",
    r"desired skills",
)

_ALL_HEADINGS = _RESPONSIBILITY_HEADINGS + _REQUIREMENT_HEADINGS


def _strip_tags(html: str) -> str:
    return _re.sub(r"<[^>]+>", " ", html)


def _extract_bullets(html: str) -> list[str]:
    """Collect <li> items from a raw JD slice (html), falling back to
    line/semicolon splitting for plain text."""
    items = [
        _strip_tags(m).strip()
        for m in _re.findall(r"<li[^>]*>(.*?)</li>", html, _re.DOTALL | _re.IGNORECASE)
    ]
    items = [i for i in items if i]
    if items:
        return items
    # Plain-text fallback: lines (or semicolon-separated clauses) that are
    # not headings.
    chunks = [ln.strip() for ln in html.splitlines() if ln.strip()] or [
        p.strip() for p in html.split(";") if p.strip()
    ]
    flat: list[str] = []
    for chunk in chunks:
        flat.extend(p.strip() for p in chunk.split(";") if p.strip())
    # Drop leading punctuation left by inline headings ("Key Responsibilities: ...").
    lines = [_re.sub(r"^[\s:;.,\-—•]+", "", c) for c in flat]
    return [ln for ln in lines if ln][:40]


def _jd_plain(opp: Optional[dict[str, Any]], cache: dict[str, Any]) -> Optional[str]:
    """Readable plain-text JD via the single normalization boundary.

    Source order: copilot description_text, search-cache description
    (frequently HTML), copilot description_html.  The normalized text is
    what every consumer (UI + CLI) renders — raw markup never surfaces as
    user-facing content.
    """
    from control_center.jd_normalizer import normalize_jd_to_text

    raw = (
        (opp.get("description_text") if opp else None)
        or cache.get("description")
        or (opp.get("description_html") if opp else None)
    )
    if not raw:
        return None
    return normalize_jd_to_text(raw) or None


def _slice_at_heading(source: str, heading_regexes: tuple[str, ...], limit: int = 3500) -> list[str]:
    """Locate the first heading match and return the bullets of the section
    that follows it (until the next known heading or the end)."""
    lower = source.lower()
    best_start = None
    best_end = None
    for pat in heading_regexes:
        m = _re.search(pat, lower)
        if m and (best_start is None or m.start() < best_start):
            best_start = m.start()
            best_end = m.end()
    if best_start is None or best_end is None:
        return []
    section = source[best_end : best_end + limit]
    # Cut at the next known heading after this one.
    next_m = _re.search(
        r"(" + "|".join(_ALL_HEADINGS) + r")", section.lower()
    )
    if next_m:
        section = section[: next_m.start()]
    return _normalize_bullets(_extract_bullets(section))


def _normalize_bullets(items: list[str]) -> list[str]:
    """Strip markup from extracted bullets via the shared normalizer and
    split <br>-separated lines into their own bullets (raw HTML slices can
    embed <br>/<li> — never surface them)."""
    from control_center.jd_normalizer import normalize_jd_to_text

    out: list[str] = []
    for item in items:
        flat = normalize_jd_to_text(item)
        for line in flat.split("\n"):
            line = line.strip()
            if line:
                out.append(line)
    return out


def extract_jd_sections(description_html: str = "", description_text: str = "") -> dict[str, list[str]]:
    """Split the stored JD into responsibilities / requirements bullet lists."""
    source = description_html or description_text or ""
    if not source:
        return {}
    result: dict[str, list[str]] = {}
    responsibilities = _slice_at_heading(source, _RESPONSIBILITY_HEADINGS)
    if responsibilities:
        result["responsibilities"] = responsibilities
    requirements = _slice_at_heading(source, _REQUIREMENT_HEADINGS)
    if requirements:
        result["requirements"] = requirements
    return result


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------


def build_job_inspection(
    job_id: str,
    *,
    lifecycle_store: Any = None,
    copilot_conn: Any = None,
    questionnaire_path: Optional[Path] = None,
    queue_path: Optional[Path] = None,
    ledger_row: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Assemble the full inspection payload for ``job_id``.

    All sources are optional-injectable for hermetic tests; production
    callers (API/CLI) use the real stores.  Returns {} when the job is not
    found in the ledger.
    """
    overview = _ledger_row(job_id) if ledger_row is None else dict(ledger_row)
    lifecycle = _lifecycle_record(job_id, store=lifecycle_store)
    cache = _search_and_score_cache(job_id)
    opp = _copilot_opportunity(job_id, conn=copilot_conn)
    questions = _questionnaire_rows(job_id, path=questionnaire_path)
    queue = _manual_queue_entries(job_id, path=queue_path)

    # A job is inspectable when ANY pipeline store knows it — the ledger only
    # tracks apply-relevant rows, so deferred/rejected/manual-review jobs
    # exist only in the lifecycle store / copilot store / run artifacts.
    if not (overview or lifecycle or opp or cache):
        return {}

    # ── Lifecycle-derived decision context ───────────────────────────
    transitions = lifecycle.get("transitions", [])
    rejection = [
        {
            "from_state": t.get("from_state"),
            "to_state": t.get("to_state"),
            "reason": t.get("reason"),
        }
        for t in reversed(transitions)
        if t.get("to_state") == "PRE_APPLICATION_REJECTED"
        or (t.get("reason") or "").lower().startswith("rejected")
        or (t.get("reason") or "").lower().startswith("deferred")
    ]
    last_reason = transitions[-1].get("reason", "") if transitions else ""

    # ── Score / ranking evidence ─────────────────────────────────────
    score = opp.get("score") if opp else None
    ranking = {
        "ai_score": cache.get("ai_score"),
        "ai_reason": cache.get("ai_reason"),
        "score": score,
        "deterministic_rank": cache.get("deterministic_rank"),
        "decision_history": cache.get("decision_history"),
        "interview_probability": opp.get("interview_probability") if opp else None,
    }
    ranking = {k: v for k, v in ranking.items() if v not in (None, "", {})}

    # ── JD / compensation / skills (copilot data_json + search cache) ─
    salary = {
        "min": opp.get("comp_min") if opp else None,
        "max": opp.get("comp_max") if opp else None,
        "currency": opp.get("currency") if opp else None,
        "notes": opp.get("comp_notes") if opp else None,
        "raw_cache": cache.get("salary"),
    }
    salary = {k: v for k, v in salary.items() if v not in (None, "", {})}
    jd = {
        "description_text": opp.get("description_text") if opp else None,
        "description_html": opp.get("description_html") if opp else None,
        "cached_description": cache.get("description"),
        "description_plain": _jd_plain(opp, cache),
        "summary": opp.get("summary") if opp else None,
        "salary": salary,
        "experience_required": opp.get("experience_required")
        if opp
        else cache.get("experience"),
        "employment_type": opp.get("employment_type") if opp else None,
        "qualifications": opp.get("qualifications") if opp else None,
        "domain_knowledge": opp.get("domain_knowledge") if opp else None,
        "effort_estimate": opp.get("effort_estimate") if opp else None,
        "market_benchmark": opp.get("market_benchmark") if opp else None,
    }
    # Deterministic responsibilities/requirements split of the STORED JD text.
    jd.update(
        extract_jd_sections(
            description_html=jd.get("description_html") or "",
            description_text=(
                jd.get("description_text")
                or jd.get("cached_description")
                or ""
            ),
        )
    )
    jd = {k: v for k, v in jd.items() if v not in (None, "", {}, [])}

    skills = {
        "required": opp.get("skills") if opp else None,
        "missing_skills": opp.get("missing_skills") if opp else None,
        "preferred_skills": opp.get("preferred_skills") if opp else None,
        "tags": cache.get("tags"),
    }
    skills = {k: v for k, v in skills.items() if v not in (None, "", [], {})}

    classification = {
        "priority": overview.get("priority") or cache.get("priority"),
        "subtrack": overview.get("subtrack") or cache.get("subtrack"),
        "role_family": (cache.get("deterministic_rank") or {}).get("role_family"),
        "ai_depth": (cache.get("deterministic_rank") or {}).get("ai_depth"),
        "fit_class": opp.get("fit_class") if opp else None,
        "industry": opp.get("industry") if opp else None,
    }
    classification = {
        k: v for k, v in classification.items() if v not in (None, "", {})
    }

    location = {
        "location": overview.get("location") or cache.get("location"),
        "remote": opp.get("remote") if opp else None,
        "city": opp.get("city") if opp else None,
        "region": opp.get("region") if opp else None,
        "country": opp.get("country") if opp else None,
        "relocation_required": opp.get("relocation_required") if opp else None,
    }
    location = {k: v for k, v in location.items() if v not in (None, "", {})}

    qentry = queue[0] if queue else {}
    urls = {
        "provider": (
            overview.get("source")
            or (opp.get("provider_id") if opp else None)
            or qentry.get("provider_id")
        ),
        "apply_url": (
            (opp.get("apply_url") if opp else None)
            or cache.get("apply_url")
            or qentry.get("apply_url")
            or qentry.get("url")
        ),
        "canonical_url": (
            (opp.get("canonical_url") if opp else None) or qentry.get("canonical_url")
        ),
        "careers_url": (
            (opp.get("careers_url") if opp else None) or qentry.get("careers_url")
        ),
        "company_domain": opp.get("company_domain") if opp else None,
    }
    urls = {k: v for k, v in urls.items() if v not in (None, "", {})}

    status = {
        "status": overview.get("status"),
        "workflow_status": overview.get("workflow_status"),
        "lifecycle_stage": overview.get("lifecycle_stage"),
        "server_status": overview.get("server_status"),
        "server_status_at": overview.get("server_status_at"),
        "last_error": overview.get("last_error"),
    }
    status = {k: v for k, v in status.items() if v not in (None, "", {})}

    routing = {
        "application_strategy": opp.get("application_strategy") if opp else None,
        "ats_type": opp.get("ats_type") if opp else None,
        "manual_queue_entries": queue,
    }
    routing = {k: v for k, v in routing.items() if v not in (None, "", [], {})}

    return {
        "job_id": str(job_id),
        "title": overview.get("title") or (opp.get("title") if opp else None),
        "company": overview.get("company") or (opp.get("company") if opp else None),
        "location": location or None,
        "status": status or None,
        "routing": routing or None,
        "lifecycle": {
            "current_state": lifecycle.get("current_state"),
            "acquired_at": lifecycle.get("acquired_at"),
            "terminal_at": lifecycle.get("terminal_at"),
            "pipeline_job_id": lifecycle.get("pipeline_job_id"),
            "score": lifecycle.get("score"),
            "last_reason": last_reason,
            "rejection_or_deferral_reasons": rejection,
            "transitions": transitions,
        },
        "classification": classification or None,
        "score_and_ranking": ranking or None,
        "jd": jd or None,
        "skills": skills or None,
        "questionnaire": {
            "unresolved": [q for q in questions if q.get("resolution_status") == "unresolved"],
            "resolved": [q for q in questions if q.get("resolution_status") != "unresolved"],
            "all": questions,
        },
        "source_and_urls": urls,
        "timestamps": {
            k: overview.get(k)
            for k in (
                "first_seen_at",
                "last_updated_at",
                "applied_at",
                "submitted_at",
                "viewed_at",
                "shortlisted_at",
                "interview_at",
                "rejected_at",
                "offer_at",
                "lifecycle_updated_at",
            )
        },
        "events": _application_events(job_id),
    }
