"""
src/application/enrichment.py
=============================

Detail-enrichment policy for the acquisition pipeline.

``should_fetch_details()`` determines whether a given (job, provider) pair
warrants a separate detail-fetch API call.  ``fetch_and_enrich()`` runs
the concurrent fetch loop, replacing the inline logic that previously lived
in ``legacy_apply_agent.enrich_jobs_with_details()``.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def should_fetch_details(job: dict, provider: Any) -> bool:
    """Should we call ``get_job_details()`` for *job*?

    Returns ``False`` when:
    * The provider is ``None`` or has ``supports_detail_fetch == False``.
    * The job ``job_id`` starts with ``"jobspy_"`` (cross-provider guard).
    """
    if provider is None:
        return False

    # Gate on provider capability
    supports = getattr(provider, "supports_detail_fetch", False)
    if not supports:
        return False

    # Cross-provider guard: job IDs from other providers should not be
    # passed to a detail-fetch-capable provider that doesn't own them.
    job_id = str(job.get("job_id") or "").strip()
    if job_id.startswith("jobspy_"):
        return False

    return True


def fetch_and_enrich(
    jobs: list[dict],
    providers: dict[str, Any],
    detail_cache: dict[str, dict] | None = None,
    cache_manager: Any = None,
    run_dir: str | Path | None = None,
    max_workers: int = 5,
) -> list[dict]:
    """Fetch details for jobs that need enrichment.

    Parameters
    ----------
    jobs : list[dict]
        Normalised job dicts from the classifier.
    providers : dict[str, Any]
        Provider map keyed by provider_id.
    detail_cache : dict[str, dict] | None
        In-memory detail cache (legacy path).
    cache_manager : Any | None
        ``CacheManager`` instance with a ``.detail`` sub-cache.
    run_dir : str | Path | None
        Artifact run directory (for diagnostics).
    max_workers : int
        Thread pool size.

    Returns
    -------
    list[dict]
        Enriched job dicts (same order as *jobs*).  Jobs that did not
        need enrichment or failed enrichment are returned as-is.
    """
    if cache_manager:
        from src.orchestration.diagnostics import ExecutionMonitor

        rd = (
            Path(run_dir)
            if run_dir
            else Path("artifacts/runs/diagnostics_fallback")
        )
        monitor = ExecutionMonitor(
            name="detail_fetch",
            total_tasks=len(jobs),
            run_dir=rd,
        )
        monitor.start()
    else:
        monitor = None

    metrics_lock = threading.Lock()

    def _fetch_one(job_tuple: tuple[int, dict]) -> dict:
        index, job = job_tuple
        job_id = str(job.get("job_id") or "").strip()

        if not job_id:
            return job

        provider_id = job.get("provider_id", "naukri")
        provider = providers.get(provider_id)

        if not should_fetch_details(job, provider):
            return job

        if monitor:
            monitor.task_started(task_id=job_id)

        try:
            if monitor:
                monitor.task_phase("network")

            detail = None
            fingerprint = None

            if cache_manager:
                from src.cache.fingerprint import compute_detail_fetch_fingerprint

                fingerprint = compute_detail_fetch_fingerprint(
                    provider_id, job_id, ""
                )
                start_time = time.perf_counter()
                record = cache_manager.detail.get(fingerprint)
                cache_manager.track_lookup(
                    (time.perf_counter() - start_time) * 1000
                )

                if record:
                    if monitor:
                        monitor.task_phase("parsing")
                    try:
                        detail = json.loads(record["content"])
                        with metrics_lock:
                            cache_manager.metrics["detail_hits"] += 1
                    except json.JSONDecodeError:
                        pass
                else:
                    with metrics_lock:
                        cache_manager.metrics["detail_misses"] += 1
            elif detail_cache is not None:
                detail = detail_cache.get(job_id)

            if detail is None:
                detail = provider.get_job_details(job_id)
                if detail:
                    if monitor:
                        monitor.task_phase("persistence")
                    if cache_manager and fingerprint:
                        start_time = time.perf_counter()
                        cache_manager.detail.set(
                            fingerprint=fingerprint,
                            provider=provider_id,
                            job_id=job_id,
                            content=json.dumps(detail),
                        )
                        cache_manager.track_save(
                            (time.perf_counter() - start_time) * 1000
                        )
                    elif detail_cache is not None:
                        with metrics_lock:
                            detail_cache[job_id] = detail

            if monitor:
                monitor.task_phase("extraction")

            full_description = _extract_job_detail_description(detail)
            if full_description:
                job["description"] = full_description

            # Preserve richer location / work-mode evidence
            job_data = detail.get("job") or {}
            detail_location = (
                job_data.get("location")
                or job_data.get("locations")
                or job_data.get("locationText")
                or detail.get("location")
            )
            if detail_location:
                if isinstance(detail_location, (list, tuple)):
                    detail_location = ", ".join(map(str, detail_location))
                job["location"] = str(detail_location)

            work_mode = (
                job_data.get("workMode")
                or job_data.get("work_mode")
                or job_data.get("workModeText")
                or detail.get("workMode")
            )
            if work_mode:
                job["work_mode"] = str(work_mode)

            job["is_external_apply"] = (
                job_data.get("responseManager") == "companyUrl"
            )

            if monitor:
                monitor.task_completed(success=True)
            return job

        except Exception as exc:
            logger.warning(
                "Job detail enrichment failed: job_id=%s error=%s",
                job_id,
                exc,
            )
            job["detail_enrichment_failed"] = True
            if monitor:
                monitor.task_completed(success=False)
            return job

    enriched = [None] * len(jobs)

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:
        futures = {
            executor.submit(_fetch_one, (idx, job)): idx
            for idx, job in enumerate(jobs)
        }
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            try:
                enriched[idx] = future.result()
            except Exception as exc:
                logger.warning(
                    "Detail enrichment thread failed: idx=%s error=%s",
                    idx,
                    exc,
                )
                enriched[idx] = jobs[idx]

    if monitor:
        monitor.stop()

    return [j for j in enriched if j is not None]


def _extract_job_detail_description(detail: dict | None) -> str | None:
    """Extract the full description from a detail payload."""
    if not detail:
        return None

    description = detail.get("description") or ""
    return description.strip() or None


# ---------------------------------------------------------------------------
# Application Summary Display
# ---------------------------------------------------------------------------


def print_application_summary(
    *,
    submitted: int,
    manual_queue: int,
    already_applied: int,
    skipped: int,
    unsupported: int,
    policy_rejected: int = 0,
    failed: int = 0,
    manual_review: int = 0,
    total_selected: int,
) -> None:
    """Print a terminal summary of the application pipeline outcome.

    Accounting invariant::

        total_selected == submitted + manual_queue + already_applied
                        + skipped + unsupported + policy_rejected
                        + failed + manual_review
    """
    accounted = (
        submitted
        + manual_queue
        + already_applied
        + skipped
        + unsupported
        + policy_rejected
        + failed
        + manual_review
    )

    print("\n" + "=" * 54)
    print("Application Summary")
    print("=" * 54)
    print(f"  Auto Submitted      {submitted:>6}")
    print(f"  Manual Queue        {manual_queue:>6}")
    print(f"  Already Applied     {already_applied:>6}")
    print(f"  Skipped             {skipped:>6}")
    print(f"  Unsupported         {unsupported:>6}")

    if policy_rejected:
        print(f"  Policy Rejected     {policy_rejected:>6}")
    if manual_review:
        print(f"  Manual Review       {manual_review:>6}")
    if failed:
        print(f"  Failed              {failed:>6}")

    print("-" * 54)
    print(f"  Total Selected      {total_selected:>6}")

    if accounted != total_selected:
        print(f"  ⚠ MISMATCH          {accounted:>6} (accounted)")
        print(f"  Accounting mismatch: {total_selected} selected ≠ {accounted} accounted")

    print("=" * 54 + "\n")
