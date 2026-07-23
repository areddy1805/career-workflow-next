from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import ceil, exp
from typing import Any, Iterable, Sequence

RESPONSE_STAGES = {
    "VIEWED",
    "SHORTLISTED",
    "INTERVIEW",
    "REJECTED",
    "OFFER",
}

STAGE_WEIGHTS = {
    "UNKNOWN": 0.0,
    "SUBMITTED": 0.0,
    "VIEWED": 1.0,
    "REJECTED": 1.0,
    "SHORTLISTED": 3.0,
    "INTERVIEW": 6.0,
    "OFFER": 12.0,
}


@dataclass(frozen=True)
class AdaptiveStrategyConfig:
    enabled: bool = True
    minimum_applications: int = 30
    minimum_responses: int = 5
    base_minimum_score: int = 68
    base_max_applications_per_run: int | None = 5
    minimum_group_samples: int = 5
    exploration_fraction: float = 0.20
    freshness_weight: float = 2.5
    experience_penalty_weight: float = 5.0

    # Phase 2 optimization controls.
    prior_strength: float = 8.0
    decay_half_life_days: float = 45.0
    response_weight: float = 1.0
    outcome_weight: float = 1.0
    preferred_group_limit: int = 3
    freshness_weight: float = 2.5
    experience_penalty_weight: float = 5.0


@dataclass(frozen=True)
class GroupPerformance:
    name: str
    applications: int
    responses: int
    weighted_outcome: float
    raw_response_rate: float
    smoothed_response_rate: float
    decayed_outcome_score: float
    utility: float


@dataclass(frozen=True)
class AdaptiveStrategy:
    active: bool
    reason: str
    total_applications: int
    total_responses: int
    minimum_score: int
    max_applications_per_run: int | None
    preferred_priorities: tuple[str, ...] = ()
    preferred_subtracks: tuple[str, ...] = ()
    exploration_fraction: float = 0.20
    freshness_weight: float = 2.5
    experience_penalty_weight: float = 5.0
    priority_performance: dict[str, GroupPerformance] = field(default_factory=dict)
    subtrack_performance: dict[str, GroupPerformance] = field(default_factory=dict)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def _age_decay(
    row: dict[str, Any],
    *,
    now: datetime,
    half_life_days: float,
) -> float:
    timestamp = (
        _parse_datetime(row.get("lifecycle_updated_at"))
        or _parse_datetime(row.get("server_status_at"))
        or _parse_datetime(row.get("applied_at"))
        or _parse_datetime(row.get("first_seen_at"))
    )

    if timestamp is None or half_life_days <= 0:
        return 1.0

    age_days = max(
        0.0,
        (now - timestamp).total_seconds() / 86400.0,
    )

    return exp(-0.6931471805599453 * age_days / half_life_days)


def _is_response(stage: str) -> bool:
    return stage in RESPONSE_STAGES


def _group_performance(
    rows: Sequence[dict[str, Any]],
    *,
    dimension: str,
    config: AdaptiveStrategyConfig,
    global_response_rate: float,
    now: datetime,
) -> dict[str, GroupPerformance]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        value = str(row.get(dimension) or "").strip()

        if not value:
            continue

        grouped.setdefault(value, []).append(row)

    result: dict[str, GroupPerformance] = {}

    for name, group_rows in grouped.items():
        applications = len(group_rows)

        responses = sum(
            1
            for row in group_rows
            if _is_response(str(row.get("lifecycle_stage") or "UNKNOWN"))
        )

        raw_response_rate = responses / applications if applications else 0.0

        smoothed_response_rate = (
            responses + config.prior_strength * global_response_rate
        ) / (applications + config.prior_strength)

        decayed_weight = 0.0
        decayed_outcome = 0.0

        for row in group_rows:
            stage = str(row.get("lifecycle_stage") or "UNKNOWN")

            decay = _age_decay(
                row,
                now=now,
                half_life_days=config.decay_half_life_days,
            )

            decayed_weight += decay
            decayed_outcome += STAGE_WEIGHTS.get(stage, 0.0) * decay

        decayed_outcome_score = (
            decayed_outcome / decayed_weight if decayed_weight else 0.0
        )

        utility = (
            config.response_weight * smoothed_response_rate
            + config.outcome_weight
            * (decayed_outcome_score / max(STAGE_WEIGHTS.values()))
        )

        result[name] = GroupPerformance(
            name=name,
            applications=applications,
            responses=responses,
            weighted_outcome=sum(
                STAGE_WEIGHTS.get(
                    str(row.get("lifecycle_stage") or "UNKNOWN"),
                    0.0,
                )
                for row in group_rows
            ),
            raw_response_rate=raw_response_rate,
            smoothed_response_rate=smoothed_response_rate,
            decayed_outcome_score=decayed_outcome_score,
            utility=utility,
        )

    return result


def _preferred_groups(
    performance: dict[str, GroupPerformance],
    *,
    minimum_group_samples: int,
    limit: int,
) -> tuple[str, ...]:
    eligible = [
        item
        for item in performance.values()
        if item.applications >= minimum_group_samples
    ]

    eligible.sort(
        key=lambda item: (
            item.utility,
            item.smoothed_response_rate,
            item.applications,
            item.name,
        ),
        reverse=True,
    )

    return tuple(item.name for item in eligible[:limit] if item.utility > 0.0)


def build_adaptive_strategy(
    rows: Iterable[dict[str, Any]],
    *,
    config: AdaptiveStrategyConfig | None = None,
    now: datetime | None = None,
) -> AdaptiveStrategy:
    config = config or AdaptiveStrategyConfig()
    population = list(rows)
    now = now or datetime.now(UTC)

    total_applications = len(population)
    total_responses = sum(
        1
        for row in population
        if _is_response(str(row.get("lifecycle_stage") or "UNKNOWN"))
    )

    if not config.enabled:
        return AdaptiveStrategy(
            active=False,
            reason="disabled",
            total_applications=total_applications,
            total_responses=total_responses,
            minimum_score=config.base_minimum_score,
            max_applications_per_run=config.base_max_applications_per_run,
            exploration_fraction=config.exploration_fraction,
            freshness_weight=config.freshness_weight,
            experience_penalty_weight=config.experience_penalty_weight,
        )

    if total_applications < config.minimum_applications:
        return AdaptiveStrategy(
            active=False,
            reason="insufficient_applications",
            total_applications=total_applications,
            total_responses=total_responses,
            minimum_score=config.base_minimum_score,
            max_applications_per_run=config.base_max_applications_per_run,
            exploration_fraction=config.exploration_fraction,
            freshness_weight=config.freshness_weight,
            experience_penalty_weight=config.experience_penalty_weight,
        )

    if total_responses < config.minimum_responses:
        return AdaptiveStrategy(
            active=False,
            reason="insufficient_response_sample",
            total_applications=total_applications,
            total_responses=total_responses,
            minimum_score=config.base_minimum_score,
            max_applications_per_run=config.base_max_applications_per_run,
            exploration_fraction=config.exploration_fraction,
            freshness_weight=config.freshness_weight,
            experience_penalty_weight=config.experience_penalty_weight,
        )

    global_response_rate = (
        total_responses / total_applications if total_applications else 0.0
    )

    minimum_score = config.base_minimum_score

    max_applications_per_run = config.base_max_applications_per_run

    # Preserve the original adaptive policy contract:
    #
    # < 5% response rate:
    #     tighten score threshold to at least 75
    #
    # >= 20% response rate:
    #     expand run capacity by one application
    #
    # Middle range:
    #     preserve configured baseline policy

    if global_response_rate < 0.05:
        minimum_score = max(
            config.base_minimum_score,
            75,
        )

        if config.base_max_applications_per_run is not None:
            max_applications_per_run = max(
                1,
                config.base_max_applications_per_run - 1,
            )

    elif (
        global_response_rate >= 0.20
        and config.base_max_applications_per_run is not None
    ):
        max_applications_per_run = config.base_max_applications_per_run + 1

    priority_performance = _group_performance(
        population,
        dimension="priority",
        config=config,
        global_response_rate=global_response_rate,
        now=now,
    )

    subtrack_performance = _group_performance(
        population,
        dimension="subtrack",
        config=config,
        global_response_rate=global_response_rate,
        now=now,
    )

    preferred_priorities = _preferred_groups(
        priority_performance,
        minimum_group_samples=config.minimum_group_samples,
        limit=config.preferred_group_limit,
    )

    preferred_subtracks = _preferred_groups(
        subtrack_performance,
        minimum_group_samples=config.minimum_group_samples,
        limit=config.preferred_group_limit,
    )

    return AdaptiveStrategy(
        active=True,
        reason="sufficient_outcome_evidence",
        total_applications=total_applications,
        total_responses=total_responses,
        minimum_score=minimum_score,
        max_applications_per_run=max_applications_per_run,
        preferred_priorities=preferred_priorities,
        preferred_subtracks=preferred_subtracks,
        exploration_fraction=max(
            0.0,
            min(
                1.0,
                config.exploration_fraction,
            ),
        ),
        freshness_weight=config.freshness_weight,
        experience_penalty_weight=config.experience_penalty_weight,
        priority_performance=priority_performance,
        subtrack_performance=subtrack_performance,
    )


def _candidate_adaptive_score(
    job: Any,
    *,
    score_map: dict[str, dict[str, Any]],
    strategy: AdaptiveStrategy,
) -> tuple[float, float, str]:
    job_id = str(job.job_id)
    meta = score_map.get(job_id, {})

    base_score = float(meta.get("score") or 0)
    priority = str(meta.get("priority") or "")
    subtrack = str(meta.get("subtrack") or "")

    days_old = int(meta.get("days_old", 7))
    exp_min = int(meta.get("experience_min", 0))

    bonus = 0.0

    # Freshness boost: being applicant #40 is better than #900.
    bonus += max(0, 7 - days_old) * strategy.freshness_weight

    # Experience penalty: softly penalize roles asking for more than 6 years.
    if exp_min > 6:
        bonus -= (exp_min - 6) * strategy.experience_penalty_weight

    priority_perf = strategy.priority_performance.get(priority)
    if priority_perf is not None:
        bonus += 20.0 * priority_perf.utility

    subtrack_perf = strategy.subtrack_performance.get(subtrack)
    if subtrack_perf is not None:
        bonus += 20.0 * subtrack_perf.utility

    if priority in strategy.preferred_priorities:
        bonus += 3.0

    if subtrack in strategy.preferred_subtracks:
        bonus += 3.0

    return (
        base_score + bonus,
        base_score,
        job_id,
    )


def rank_candidates_adaptively(
    jobs: Sequence[Any],
    *,
    score_map: dict[str, dict[str, Any]],
    strategy: AdaptiveStrategy,
) -> list[Any]:
    ranked = list(jobs)

    if not strategy.active:
        return ranked

    ranked.sort(
        key=lambda job: _candidate_adaptive_score(
            job,
            score_map=score_map,
            strategy=strategy,
        ),
        reverse=True,
    )

    return ranked


def select_candidates_with_exploration(
    jobs: Sequence[Any],
    *,
    score_map: dict[str, dict[str, Any]],
    strategy: AdaptiveStrategy,
    limit: int,
) -> list[Any]:
    """
    Deterministic explore/exploit allocation.

    Exploitation takes the highest adaptive-ranked candidates from historically
    preferred cohorts. Exploration reserves a bounded quota for candidates
    outside those cohorts, ordered by base score. No randomness is used, so
    repeated runs over the same inputs are reproducible.
    """
    if limit <= 0:
        return []

    candidates = list(jobs)

    if not strategy.active:
        return candidates[:limit]

    exploration_slots = min(
        limit,
        ceil(limit * strategy.exploration_fraction),
    )

    exploitation_slots = limit - exploration_slots

    preferred: list[Any] = []
    exploratory: list[Any] = []

    for job in candidates:
        meta = score_map.get(str(job.job_id), {})
        priority = str(meta.get("priority") or "")
        subtrack = str(meta.get("subtrack") or "")

        if (
            priority in strategy.preferred_priorities
            or subtrack in strategy.preferred_subtracks
        ):
            preferred.append(job)
        else:
            exploratory.append(job)

    selected = preferred[:exploitation_slots]

    exploratory.sort(
        key=lambda job: (
            float(
                score_map.get(
                    str(job.job_id),
                    {},
                ).get("score")
                or 0
            ),
            str(job.job_id),
        ),
        reverse=True,
    )

    selected.extend(exploratory[:exploration_slots])

    if len(selected) < limit:
        selected_ids = {str(job.job_id) for job in selected}

        for job in candidates:
            if str(job.job_id) in selected_ids:
                continue

            selected.append(job)
            selected_ids.add(str(job.job_id))

            if len(selected) >= limit:
                break

    return selected[:limit]


def strategy_audit_payload(
    strategy: AdaptiveStrategy,
) -> dict[str, Any]:
    return {
        "active": strategy.active,
        "reason": strategy.reason,
        "total_applications": strategy.total_applications,
        "total_responses": strategy.total_responses,
        "minimum_score": strategy.minimum_score,
        "max_applications_per_run": (strategy.max_applications_per_run),
        "exploration_fraction": strategy.exploration_fraction,
        "preferred_priorities": list(strategy.preferred_priorities),
        "preferred_subtracks": list(strategy.preferred_subtracks),
        "priority_utilities": {
            name: round(item.utility, 6)
            for name, item in strategy.priority_performance.items()
        },
        "subtrack_utilities": {
            name: round(item.utility, 6)
            for name, item in strategy.subtrack_performance.items()
        },
    }
