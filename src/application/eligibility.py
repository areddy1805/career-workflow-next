from __future__ import annotations

import os
from typing import Any


def _job_id(job: Any) -> str:
    if isinstance(job, dict):
        return str(job.get("job_id") or "")
    return str(getattr(job, "job_id", "") or "")


def _job_title(job: Any) -> str:
    if isinstance(job, dict):
        return str(job.get("title") or "")
    return str(getattr(job, "title", "") or "")


def _job_company(job: Any) -> str:
    if isinstance(job, dict):
        return str(job.get("company") or "")
    return str(getattr(job, "company", "") or "")


def _score_for_job(
    job: Any,
    score_map: dict[str, dict],
) -> int:
    result = score_map.get(_job_id(job), {})

    try:
        return int(
            result.get(
                "score",
                result.get("ai_score", 0),
            )
            or 0
        )
    except (TypeError, ValueError):
        return 0


def evaluate_auto_apply_eligibility(
    job: Any,
    *,
    score_map: dict[str, dict],
    minimum_score: int | None = None,
) -> dict:
    """
    Broad-coverage application policy.

    At this stage, all classified candidates are eligible.

    Location/work-mode is the only hard application gate and is enforced
    upstream by JobClassifier.location_work_mode_gate().

    Score, seniority, experience, stack fit, education, salary, and company
    are ranking/audit signals only.
    """
    if minimum_score is None:
        minimum_score = int(os.getenv("AUTO_APPLY_MIN_SCORE", "0"))

    return {
        "job_id": _job_id(job),
        "title": _job_title(job),
        "company": _job_company(job),
        "score": _score_for_job(job, score_map),
        "minimum_score": minimum_score,
        "score_is_ranking_only": True,
        "eligible": True,
        "reasons": [],
        "primary_reason": None,
    }


def annotate_auto_apply_eligibility(
    jobs: list[Any],
    *,
    score_map: dict[str, dict],
    minimum_score: int | None = None,
) -> tuple[list[Any], list[dict]]:
    decisions = [
        evaluate_auto_apply_eligibility(
            job,
            score_map=score_map,
            minimum_score=minimum_score,
        )
        for job in jobs
    ]

    return list(jobs), decisions


def eligibility_rejection_summary(
    decisions: list[dict],
) -> dict[str, int]:
    return {}
