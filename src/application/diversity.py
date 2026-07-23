from __future__ import annotations

import hashlib
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class DiversityPolicy:
    max_per_company_per_run: int = 2
    max_per_role_family_per_company: int = 1
    max_per_vacancy_fingerprint: int = 1


def _value(job: Any, name: str, default: str = "") -> str:
    if isinstance(job, dict):
        return str(job.get(name, default) or default)
    return str(getattr(job, name, default) or default)


def normalize_company(value: str) -> str:
    text = re.sub(
        r"\b(pvt|private|ltd|limited|llp|inc|corp|corporation)\b",
        " ",
        (value or "").lower(),
    )
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def normalize_role_family(value: str) -> str:
    text = (value or "").lower()
    text = re.sub(
        r"\b(senior|sr|junior|jr|lead|principal|staff|hiring for|opening at|immediate joiner)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9+#]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_location(value: str) -> str:
    text = (value or "").lower()
    text = re.sub(r"\b(all areas|all india|india|multiple locations?)\b", " ", text)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def normalize_experience(value: str) -> str:
    numbers = re.findall(r"\d+", value or "")
    return "-".join(numbers[:2])


def normalize_tag_signature(job: Any) -> str:
    if isinstance(job, dict):
        raw_tags = job.get("tags") or []
    else:
        raw_tags = getattr(job, "tags", None) or []

    if isinstance(raw_tags, str):
        raw_tags = re.split(r"[,|]", raw_tags)

    normalized = {
        re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#.]+", " ", str(tag).lower())).strip()
        for tag in raw_tags
        if str(tag).strip()
    }
    return ",".join(sorted(tag for tag in normalized if tag))


def vacancy_fingerprint(job: Any) -> str:
    return "|".join(
        (
            normalize_company(_value(job, "company")),
            normalize_role_family(_value(job, "title")),
            normalize_location(_value(job, "location")),
            normalize_experience(_value(job, "experience")),
            normalize_tag_signature(job),
        )
    )


def vacancy_family_fingerprint(job: Any) -> str:
    """Cheap pre-detail grouping key. Location is intentionally excluded."""
    return "|".join(
        (
            normalize_company(_value(job, "company")),
            normalize_role_family(_value(job, "title")),
        )
    )


def normalize_description(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = text.lower()
    text = re.sub(r"\b(atci|req|requisition|job id)[- :#]*[a-z0-9-]+\b", " ", text)
    text = re.sub(r"\b\d{6,}\b", " ", text)
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def description_fingerprint(job: Any) -> str:
    normalized = normalize_description(_value(job, "description"))
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def exclude_job_ids(jobs: Iterable[Any], excluded_ids: set[str]) -> list[Any]:
    excluded = {str(value) for value in excluded_ids}
    return [job for job in jobs if _value(job, "job_id") not in excluded]


def allocate_detail_budget(
    jobs: list[Any],
    *,
    budget: int,
    max_per_company: int = 8,
    max_per_family: int = 2,
) -> list[Any]:
    """
    Allocate detail-fetch budget with diversity-first ordering.

    Company and role-family caps shape the first pass only.
    Candidates exceeding those caps are retained in overflow and used
    to backfill any remaining budget.

    This function must not silently discard otherwise eligible jobs.
    """
    if budget < 1:
        return []

    company_queues: dict[str, deque[Any]] = defaultdict(deque)
    company_order: list[str] = []

    family_counts: dict[str, int] = defaultdict(int)
    overflow: list[Any] = []

    for job in jobs:
        company = normalize_company(_value(job, "company")) or "__unknown__"
        family = vacancy_family_fingerprint(job)

        if family_counts[family] >= max_per_family:
            overflow.append(job)
            continue

        family_counts[family] += 1

        if company not in company_queues:
            company_order.append(company)

        company_queues[company].append(job)

    selected: list[Any] = []
    selected_ids: set[str] = set()
    company_counts: dict[str, int] = defaultdict(int)

    active = deque(company_order)

    while active and len(selected) < budget:
        company = active.popleft()
        queue = company_queues[company]

        if queue and company_counts[company] < max_per_company:
            job = queue.popleft()
            selected.append(job)
            selected_ids.add(str(_value(job, "job_id")))
            company_counts[company] += 1

        if queue and company_counts[company] < max_per_company:
            active.append(company)

    for company in company_order:
        queue = company_queues[company]

        while queue:
            overflow.append(queue.popleft())

    for job in overflow:
        if len(selected) >= budget:
            break

        job_id = str(_value(job, "job_id"))

        if job_id in selected_ids:
            continue

        selected.append(job)
        selected_ids.add(job_id)

    return selected


def deduplicate_enriched_jobs(jobs: list[Any]) -> list[Any]:
    """Post-detail exact semantic-content suppression using normalized JD text."""
    seen_descriptions: set[str] = set()
    seen_vacancies: set[str] = set()
    result: list[Any] = []

    for job in jobs:
        description_key = description_fingerprint(job)
        vacancy_key = vacancy_fingerprint(job)
        if description_key:
            if description_key in seen_descriptions:
                continue
            seen_descriptions.add(description_key)
        elif vacancy_key in seen_vacancies:
            continue
        seen_vacancies.add(vacancy_key)
        result.append(job)

    return result


def diversify_jobs(
    jobs: list[Any],
    *,
    historical_company_counts: dict[str, int] | None = None,
    policy: DiversityPolicy | None = None,
) -> list[Any]:
    """Reorder for diversity without discarding valid opportunities.

    Company and role-family caps shape the first pass only. Overflow candidates
    are appended in ranked order. Exact vacancy fingerprints remain suppressed.
    """
    policy = policy or DiversityPolicy()
    history = historical_company_counts or {}
    company_run_counts: dict[str, int] = defaultdict(int)
    family_counts: dict[tuple[str, str], int] = defaultdict(int)
    fingerprint_counts: dict[str, int] = defaultdict(int)

    ranked = sorted(
        enumerate(jobs),
        key=lambda pair: (
            history.get(normalize_company(_value(pair[1], "company")), 0),
            pair[0],
        ),
    )

    primary: list[Any] = []
    overflow: list[Any] = []

    for _, job in ranked:
        company = normalize_company(_value(job, "company"))
        family = normalize_role_family(_value(job, "title"))
        fingerprint = vacancy_fingerprint(job)

        if fingerprint_counts[fingerprint] >= policy.max_per_vacancy_fingerprint:
            continue
        fingerprint_counts[fingerprint] += 1

        within_company = company_run_counts[company] < policy.max_per_company_per_run
        within_family = (
            family_counts[(company, family)] < policy.max_per_role_family_per_company
        )

        if within_company and within_family:
            primary.append(job)
            company_run_counts[company] += 1
            family_counts[(company, family)] += 1
        else:
            overflow.append(job)

    return primary + overflow
