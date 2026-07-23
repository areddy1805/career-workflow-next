"""
src/acquisition/merge.py
=========================

Cross-provider job deduplication and merging.

This module must not import from apply_agent to avoid circular dependencies.
"""

from __future__ import annotations

import difflib
import logging
import re

from src.acquisition.providers.jobspy_provider import canonicalize_url

logger = logging.getLogger(__name__)


def _normalise_for_dedup(text: str) -> str:
    """Lowercase and collapse whitespace for deduplication comparisons."""
    return re.sub(r"\s+", " ", str(text).lower().strip())


def merge_jobs(
    naukri_jobs: list,
    jobspy_jobs: list,
    provider_priority: list[str],
) -> list:
    """
    Merge Naukri and JobSpy job lists into a single deduplicated list.

    Deduplication strategy (three tiers, per JOBSPY_DISCOVERY.md §7):

    1. Canonical URL match  — identical canonicalized apply_link.
    2. Exact title + company + location match  — case-insensitive.
    3. Fuzzy match on title + company + location  — SequenceMatcher ≥ 0.85.

    When a duplicate is found:
    * The provider listed first in provider_priority supplies the metadata.
    * Both source tags are appended to the winning job's tags list for lineage.

    Naukri jobs are always iterated first because they have authenticated
    apply links and richer metadata.  provider_priority merely determines
    which metadata wins if both are present for the same duplicate.
    """
    if not jobspy_jobs:
        return list(naukri_jobs)

    def _provider_rank(job) -> int:
        """Lower rank = higher priority."""
        source = getattr(job, "provider_source", "unknown")
        if source == "unknown":
            job_id = str(getattr(job, "job_id", ""))
            if job_id.startswith("jobspy_indeed_"):
                source = "indeed"
            elif job_id.startswith("jobspy_linkedin_"):
                source = "linkedin"
            elif job_id.startswith("jobspy_google_"):
                source = "google"
            else:
                source = "naukri"
        try:
            return provider_priority.index(source)
        except ValueError:
            return len(provider_priority)

    def _canonical_url(job) -> str:
        url = str(getattr(job, "apply_url", "") or "")
        return canonicalize_url(url) if url else ""

    def _identity_key(job) -> tuple[str, str, str]:
        return (
            _normalise_for_dedup(getattr(job, "title", "")),
            _normalise_for_dedup(getattr(job, "company", "")),
            _normalise_for_dedup(getattr(job, "location", "")),
        )

    def _fuzzy_score(a: tuple, b: tuple) -> float:
        combined_a = " ".join(a)
        combined_b = " ".join(b)
        return difflib.SequenceMatcher(None, combined_a, combined_b).ratio()

    FUZZY_THRESHOLD = 0.85

    # Index existing Naukri jobs
    merged: list = list(naukri_jobs)
    url_index: dict[str, int] = {}  # canonical_url → index in merged
    key_index: dict[tuple, int] = {}  # (title, company, location) → index in merged

    for idx, job in enumerate(merged):
        url = _canonical_url(job)
        if url:
            url_index[url] = idx
        key_index[_identity_key(job)] = idx

    def _source_tag(job) -> str:
        source = getattr(job, "provider_source", "unknown")
        if source != "unknown":
            return f"source:{source}"
        job_id = str(getattr(job, "job_id", ""))
        for site in ("indeed", "linkedin", "google"):
            if f"jobspy_{site}_" in job_id:
                return f"source:{site}"
        return "source:naukri"

    for jobspy_job in jobspy_jobs:
        url = _canonical_url(jobspy_job)
        key = _identity_key(jobspy_job)
        dup_idx: int | None = None

        # Tier 1 — canonical URL
        if url and url in url_index:
            dup_idx = url_index[url]

        # Tier 2 — exact key
        if dup_idx is None and key in key_index:
            dup_idx = key_index[key]

        # Tier 3 — fuzzy
        if dup_idx is None:
            for idx, existing in enumerate(merged):
                score = _fuzzy_score(key, _identity_key(existing))
                if score >= FUZZY_THRESHOLD:
                    dup_idx = idx
                    break

        if dup_idx is None:
            # Genuinely new job — add it
            new_idx = len(merged)
            merged.append(jobspy_job)
            if url:
                url_index[url] = new_idx
            key_index[key] = new_idx
            continue

        # Duplicate — resolve by provider_priority
        existing_job = merged[dup_idx]
        winning_job = (
            jobspy_job
            if _provider_rank(jobspy_job) < _provider_rank(existing_job)
            else existing_job
        )

        # Merge source tags so analytics can measure crossover coverage
        existing_tags = list(getattr(existing_job, "tags", []) or [])
        new_tag = _source_tag(jobspy_job)
        if new_tag not in existing_tags:
            existing_tags.append(new_tag)

        existing_naukri_tag = _source_tag(existing_job)
        if existing_naukri_tag not in existing_tags:
            existing_tags.append(existing_naukri_tag)

        winning_job.tags = existing_tags
        merged[dup_idx] = winning_job

        logger.debug(
            "Duplicate resolved: %r vs %r → kept %r (priority %d vs %d)",
            getattr(existing_job, "job_id", ""),
            getattr(jobspy_job, "job_id", ""),
            getattr(winning_job, "job_id", ""),
            _provider_rank(existing_job),
            _provider_rank(jobspy_job),
        )

    return merged
