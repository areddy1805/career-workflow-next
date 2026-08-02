"""Pipeline → Copilot opportunity-store sync (integration).

Every successful pipeline run populates the Copilot opportunity store
(``copilot.db``) so the Copilot Inbox mirrors the live pipeline pool — no
manual ingestion ever needed:

    Pipeline → JobLifecycleStore (canonical acquired jobs)
             → CopilotOpportunity (via ``oppstore.upsert``, the existing
               copilot store API)
             → ``copilot_opportunities`` → API → Inbox

Design constraints honored:
- Lives on the pipeline side; consumes only the copilot package's public
  store/model APIs (ADR-007: copilot.db writes stay inside existing copilot
  APIs). The copilot package itself is untouched.
- Idempotent: re-syncing the same job merges on fingerprint (oppstore
  semantics), so a second run updates status/provenance instead of
  duplicating.
- Best-effort: a sync failure logs a warning and never fails the run.
"""

from __future__ import annotations

import logging
from typing import Any

from src.copilot.constants import OpportunitySource, OpportunityStatusView
from src.copilot.db.db import open_copilot_db
from src.copilot.oppstore import store as oppstore
from src.copilot.oppstore.model import CopilotOpportunity
from src.orchestration.job_lifecycle import JobLifecycleStore, JobState

logger = logging.getLogger("orchestration.copilot_sync")

# Provider ids seen from the pipeline's acquisition engine → frozen source
# vocabulary (03_OPPORTUNITY_MODEL.md §2). Unknown providers bucket as
# generic_url (the Inbox source filter still groups them).
_PROVIDER_TO_SOURCE: dict[str, str] = {
    "linkedin": OpportunitySource.LINKEDIN_URL.value,
    "wellfound": OpportunitySource.WELLFOUND_URL.value,
    "greenhouse": OpportunitySource.GREENHOUSE.value,
    "lever": OpportunitySource.LEVER.value,
    "ashby": OpportunitySource.ASHBY.value,
    "workday": OpportunitySource.WORKDAY.value,
    "rippling": OpportunitySource.RIPPLING.value,
    "naukri": OpportunitySource.GENERIC_URL.value,
    "jobspy": OpportunitySource.GENERIC_URL.value,
    "careers": OpportunitySource.CAREERS_URL.value,
}

# Lifecycle state → frozen status view (ADR-012). Coarse, deterministic;
# the copilot status_view reconcile refines it later from the ledger.
_STATE_TO_VIEW: dict[str, str] = {
    JobState.ACQUIRED.value: OpportunityStatusView.NEW.value,
    JobState.CLASSIFYING.value: OpportunityStatusView.NEW.value,
    JobState.ELIGIBLE.value: OpportunityStatusView.NEW.value,
    JobState.SELECTED_AUTO.value: OpportunityStatusView.APPLYING.value,
    JobState.APPLYING.value: OpportunityStatusView.APPLYING.value,
    JobState.DEFERRED.value: OpportunityStatusView.APPLYING.value,
    JobState.SUBMITTED.value: OpportunityStatusView.SUBMITTED.value,
    JobState.ALREADY_APPLIED.value: OpportunityStatusView.SUBMITTED.value,
    JobState.ROUTED_MANUAL.value: OpportunityStatusView.TRACKING.value,
    JobState.ROUTED_ATS.value: OpportunityStatusView.TRACKING.value,
    JobState.ROUTED_EXTERNAL.value: OpportunityStatusView.TRACKING.value,
    JobState.QUEUED.value: OpportunityStatusView.TRACKING.value,
    JobState.APPLICATION_FAILED.value: OpportunityStatusView.CLOSED.value,
    JobState.PRE_APPLICATION_REJECTED.value: OpportunityStatusView.CLOSED.value,
    JobState.ROUTED_UNSUPPORTED.value: OpportunityStatusView.CLOSED.value,
}


def _provider_to_source(provider_id: str | None) -> str:
    if not provider_id:
        return OpportunitySource.GENERIC_URL.value
    return _PROVIDER_TO_SOURCE.get(
        provider_id.lower(), OpportunitySource.GENERIC_URL.value
    )


def _state_to_view(state: JobState | str) -> str:
    value = state.value if isinstance(state, JobState) else str(state)
    return _STATE_TO_VIEW.get(value, OpportunityStatusView.NEW.value)


def sync_pipeline_jobs_to_copilot(
    lifecycle: JobLifecycleStore,
    jobs_by_id: dict[str, dict[str, Any]] | None = None,
) -> int:
    """Upsert every job in the lifecycle store into the copilot store.

    ``jobs_by_id`` optionally carries enriched fields (apply_url, location,
    score) keyed by job id; identity/state come from the lifecycle store —
    the canonical record of every acquired job.

    Returns the number of upserted opportunities. Best-effort: raises
    nothing on copilot-store failures (the caller logs).
    """
    jobs_by_id = jobs_by_id or {}
    conn = open_copilot_db()
    synced = 0
    try:
        for record in lifecycle.all_records():
            jid = record.job_id
            if not jid:
                continue
            extra = jobs_by_id.get(jid, {})
            opportunity = CopilotOpportunity(
                source=_provider_to_source(record.provider_id),
                title=record.title or extra.get("title") or jid,
                company=record.company or extra.get("company") or "Unknown",
                opportunity_id=jid,
                provider_id=record.provider_id or "",
                provider_job_id=jid,
                apply_url=extra.get("apply_url") or extra.get("apply_link") or None,
                status_view=_state_to_view(record.current_state),
            )
            oppstore.upsert(conn, opportunity)
            if record.pipeline_job_id:
                oppstore.set_pipeline_job_id(conn, jid, record.pipeline_job_id)
            # The merge keeps first-seen values on ties; a changed lifecycle
            # state is written explicitly so the Inbox view tracks the run.
            oppstore.set_status_view(conn, jid, opportunity.status_view)
            synced += 1
    finally:
        conn.close()
    return synced
