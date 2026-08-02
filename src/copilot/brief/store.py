"""Brief persistence, cache, and build service (CP-2-07).

Frozen ``copilot_briefs`` table (§7.8) + in-memory cache + deterministic
build (05 §3 pipeline: cache hit → return; else load persisted; else build
and persist). Build emits ``brief.generated`` (CP-0-03 events). The cache is
a plain dict keyed by opportunity_id; the durable store is the DB.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Callable

from src.copilot.brief.assembler import assemble_brief
from src.copilot.brief.effort import estimate_effort
from src.copilot.brief.llm import prose_summary
from src.copilot.brief.models import ApplicationBrief
from src.copilot.brief.probability import interview_probability
from src.copilot.brief.questions import CorpusQuestion, likely_questions
from src.copilot.brief.salary import assess_salary
from src.copilot.events.emitter import emit_event
from src.copilot.oppstore.model import CopilotOpportunity

SECTIONS_VERSION = "1"

_CACHE: dict[str, ApplicationBrief] = {}


def save_brief(conn: sqlite3.Connection, brief: ApplicationBrief) -> None:
    """Upsert one brief into ``copilot_briefs`` (frozen §7.8 shape)."""
    conn.execute(
        """
        INSERT INTO copilot_briefs
            (opportunity_id, brief_json, generated_at, model_used, sections_version)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(opportunity_id) DO UPDATE SET
            brief_json = excluded.brief_json,
            generated_at = excluded.generated_at,
            model_used = excluded.model_used,
            sections_version = excluded.sections_version
        """,
        (
            brief.opportunity_id,
            json.dumps(brief.to_dict()),
            datetime.now(timezone.utc).isoformat(),
            "llm" if "llm" in brief.section_sources.values() else "deterministic",
            SECTIONS_VERSION,
        ),
    )
    conn.commit()


def load_brief(
    conn: sqlite3.Connection, opportunity_id: str
) -> ApplicationBrief | None:
    """Read one brief from the DB, or None when absent."""
    row = conn.execute(
        "SELECT brief_json FROM copilot_briefs WHERE opportunity_id = ?",
        (opportunity_id,),
    ).fetchone()
    if row is None:
        return None
    return ApplicationBrief.from_dict(json.loads(row["brief_json"]))


def delete_brief(conn: sqlite3.Connection, opportunity_id: str) -> None:
    """Remove one brief from the DB."""
    conn.execute(
        "DELETE FROM copilot_briefs WHERE opportunity_id = ?",
        (opportunity_id,),
    )
    conn.commit()


def build_brief(
    conn: sqlite3.Connection,
    opportunity: CopilotOpportunity,
    *,
    cache: dict[str, ApplicationBrief] | None = None,
    target: tuple[float, float] | None = None,
    market_median: float | None = None,
    priors: dict[tuple[str, str, str], float] | None = None,
    corpus: list[CorpusQuestion] | None = None,
    llm_call: Callable[[str], str] | None = None,
    llm_enabled: bool = False,
) -> ApplicationBrief:
    """Deterministic build: assemble every brief section, persist, cache,
    emit ``brief.generated`` (05 §3 steps 2–7). Injectable seams mirror the
    services' defaults (priors/corpus from Answer Bank & learning store when
    they land; LLM gated off)."""
    store = cache if cache is not None else _CACHE
    salary = assess_salary(opportunity, target=target, market_median=market_median)
    effort = estimate_effort(opportunity)
    probability = interview_probability(opportunity, priors=priors)
    questions = likely_questions(opportunity, corpus=corpus)
    summary = prose_summary(
        opportunity, llm_call=llm_call, enabled=llm_enabled
    )
    brief = assemble_brief(
        opportunity,
        salary=salary,
        effort=effort,
        interview_probability=probability,
        questions=questions,
        prose_summary=summary,
    )
    save_brief(conn, brief)
    store[brief.opportunity_id] = brief
    emit_event(
        conn,
        "brief.generated",
        brief.opportunity_id,
        "opportunity",
        payload={
            "verdict": brief.verdict.value,
            "sections": sorted(brief.section_sources),
        },
    )
    return brief


def get_brief(
    conn: sqlite3.Connection,
    opportunity_id: str,
    *,
    opportunity: CopilotOpportunity | None = None,
    cache: dict[str, ApplicationBrief] | None = None,
    target: tuple[float, float] | None = None,
    market_median: float | None = None,
    priors: dict[tuple[str, str, str], float] | None = None,
    corpus: list[CorpusQuestion] | None = None,
    llm_call: Callable[[str], str] | None = None,
    llm_enabled: bool = False,
) -> ApplicationBrief | None:
    """05 §3 pipeline: cache hit → return; DB hit → cache + return; else
    build (requires ``opportunity``). Returns None only when nothing is
    cached/persisted and no opportunity was supplied."""
    store = cache if cache is not None else _CACHE
    if opportunity_id in store:
        return store[opportunity_id]
    persisted = load_brief(conn, opportunity_id)
    if persisted is not None:
        store[opportunity_id] = persisted
        return persisted
    if opportunity is None:
        return None
    return build_brief(
        conn,
        opportunity,
        cache=store,
        target=target,
        market_median=market_median,
        priors=priors,
        corpus=corpus,
        llm_call=llm_call,
        llm_enabled=llm_enabled,
    )


def invalidate_brief(
    conn: sqlite3.Connection,
    opportunity_id: str,
    *,
    cache: dict[str, ApplicationBrief] | None = None,
) -> None:
    """Drop the brief from cache and DB (forces a cold rebuild next read)."""
    store = cache if cache is not None else _CACHE
    store.pop(opportunity_id, None)
    delete_brief(conn, opportunity_id)
