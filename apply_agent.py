from __future__ import annotations

import csv
import html
import logging
import os
import re
import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from colorama import Fore, Style, init
from dotenv import load_dotenv

from config.candidate_profile import CANDIDATE_PROFILE
from src.application.router import ApplicationRouter
from src.application.capability import ProviderCapabilities
from src.application.models import RoutingStrategy
from src.application.adaptive_strategy import (
    AdaptiveStrategyConfig,
    build_adaptive_strategy,
    rank_candidates_adaptively,
    select_candidates_with_exploration,
    strategy_audit_payload,
)
from src.application.diversity import DiversityPolicy, diversify_jobs
from src.application.failure import (
    FailureKind,
    classify_application_exception,
)
from src.application.ledger import ApplicationLedger
from src.application.manual_action_queue import (
    ManualActionQueue,
)
from src.application.outcome import (
    ApplicationOutcome,
    ApplicationStatus,
)
from src.application.policy import (
    ApplicationPolicy,
    evaluate_application_policy,
)
from src.application.response_interpreter import (
    interpret_application_response,
)
from src.application.response_store import save_response
from src.orchestration.metrics import PipelineRunMetrics
from src.client.job_classifier import JobFilterPipeline2
from src.client.job_client import NaukriJobClient
from src.client.naukri_client import NaukriLoginClient
from src.exceptions.exceptions import (
    NaukriSearchChallengeError,
)
from src.llm.client import OMLXClient
from src.llm.question_resolver import LLMQuestionResolver
from src.resolution.hybrid_resolver import HybridQuestionResolver

from src.orchestration.runtime import CircuitBreaker
from src.search.planner import SearchPlanner
from src.search.challenge_cooldown import SearchChallengeCooldown
from src.search.job_search_cache import JobSearchCache
from src.utils.questionnaire_telemetry import log_unresolved_questions
from src.cache.cache_manager import CacheManager
from src.cache.fingerprint import compute_detail_fetch_fingerprint

# JobSpy acquisition — additive, isolated from Naukri path.
from src.acquisition.config import load_acquisition_config
from src.acquisition.acquisition_service import fetch_jobspy_jobs
from src.acquisition.merge import merge_jobs
from src.acquisition.providers.jobspy_provider import (
    JobSpyConfig,
    JobSpyProvider,
)

load_dotenv()
init(autoreset=True)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------------
# Persistence — applied jobs CSV
#
# A flat CSV file is used as a lightweight store for applied job IDs. This
# prevents the agent from applying to the same job on subsequent runs.
# The file is appended to, never rewritten, so historical records are preserved.
# ----------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------
# Terminal display helpers
#
# All output is routed through these functions so the visual style stays
# consistent across the run. Nothing here affects business logic.
# ----------------------------------------------------------------------------------

LINE = f"{Fore.WHITE}{'─' * 68}{Style.RESET_ALL}"
THIN = f"{Fore.WHITE}{'·' * 68}{Style.RESET_ALL}"


def print_acquisition_summary(
    jobs: list,
    fetch_result: JobFetchResult,
) -> None:
    live = 0
    cache = 0
    live_cache = 0
    unknown = 0

    for job in jobs:
        source = getattr(
            job,
            "acquisition_source",
            "unknown",
        )

        if source == "live":
            live += 1

        elif source == "cache":
            cache += 1

        elif source == "live+cache":
            live_cache += 1

        else:
            unknown += 1

    print_section_title("job acquisition summary")

    rows = [
        (
            "Final jobs",
            len(jobs),
        ),
        (
            "Live only",
            live,
        ),
        (
            "Cache only",
            cache,
        ),
        (
            "Live + cache",
            live_cache,
        ),
        (
            "Unknown source",
            unknown,
        ),
        (
            "Search requests",
            fetch_result.search_requests_attempted,
        ),
        (
            "Challenge encountered",
            fetch_result.challenge_encountered,
        ),
        (
            "Cooldown suppression",
            fetch_result.search_skipped_due_to_cooldown,
        ),
    ]

    for label, value in rows:
        print(
            f"  {Fore.WHITE}"
            f"{label:<28}"
            f"{Style.RESET_ALL}  "
            f"{Fore.CYAN}"
            f"{value}"
            f"{Style.RESET_ALL}"
        )


def print_section_title(text: str) -> None:
    # Prints a bold titled section divider. Used to mark each major phase
    # of the run (login, fetch, filter, apply, summary).
    print(f"\n{LINE}")
    print(f"  {Fore.CYAN}" f"{Style.BRIGHT}" f"{text.upper()}" f"{Style.RESET_ALL}")
    print(LINE)


def print_job_header(
    index: int,
    total: int,
    job,
    score=None,
    ai_detail=None,
) -> None:
    # Prints the full metadata block for a single job. Includes title, company,
    # job ID, URL, AI score with a visual bar, and skill tags if present.
    now = datetime.now(UTC).strftime("%Y-%m-%d  %H:%M UTC")

    score_str = ""

    if score is not None:
        score_color = (
            Fore.GREEN if score >= 70 else (Fore.YELLOW if score >= 50 else Fore.RED)
        )

        score_bar = _score_bar(score)

        score_str = (
            f"  {score_color}" f"{score}/100" f"{Style.RESET_ALL}  " f"{score_bar}"
        )

    print(f"\n{LINE}")

    print(
        f"  {Fore.CYAN}"
        f"{Style.BRIGHT}"
        f"JOB {index}/{total}"
        f"{Style.RESET_ALL}"
        f"  {Fore.WHITE}"
        f"{now}"
        f"{Style.RESET_ALL}"
    )

    print(THIN)

    print(
        f"  {Fore.WHITE}"
        f"Title   :"
        f"{Style.RESET_ALL}  "
        f"{Style.BRIGHT}"
        f"{job.title}"
        f"{Style.RESET_ALL}"
    )

    print(
        f"  {Fore.WHITE}"
        f"Company :"
        f"{Style.RESET_ALL}  "
        f"{Fore.YELLOW}"
        f"{job.company}"
        f"{Style.RESET_ALL}"
    )

    print(
        f"  {Fore.WHITE}"
        f"Job ID  :"
        f"{Style.RESET_ALL}  "
        f"{Fore.BLUE}"
        f"{job.job_id}"
        f"{Style.RESET_ALL}"
    )

    url = (
        getattr(job, "apply_link", None)
        or getattr(job, "url", None)
        or f"https://www.naukri.com/job-listings-{job.job_id}"
    )

    print(
        f"  {Fore.WHITE}"
        f"URL     :"
        f"{Style.RESET_ALL}  "
        f"{Fore.BLUE}"
        f"{url}"
        f"{Style.RESET_ALL}"
    )

    if score is not None:
        detail_text = (
            f"  {Fore.WHITE}" f"({ai_detail})" f"{Style.RESET_ALL}" if ai_detail else ""
        )

        print(
            f"  {Fore.WHITE}"
            f"Score   :"
            f"{Style.RESET_ALL}"
            f"{score_str}"
            f"{detail_text}"
        )

    if job.tags:
        tag_str = "  ".join(
            f"{Fore.CYAN}" f"[{tag}]" f"{Style.RESET_ALL}" for tag in job.tags
        )

        print(f"  {Fore.WHITE}" f"Tags    :" f"{Style.RESET_ALL}  " f"{tag_str}")


def _score_bar(
    score: int,
    width: int = 10,
) -> str:
    # Returns a small ASCII progress bar representing the AI score (0-100).
    # Color shifts from red to yellow to green as score increases.
    filled = int((score / 100) * width)

    bar = "█" * filled + "░" * (width - filled)

    color = Fore.GREEN if score >= 70 else (Fore.YELLOW if score >= 50 else Fore.RED)

    return f"{color}" f"{bar}" f"{Style.RESET_ALL}"


def print_status_applied(
    applied_at=None,
) -> None:
    ts = f"  {Fore.WHITE}" f"at {applied_at}" f"{Style.RESET_ALL}" if applied_at else ""

    print(
        f"  {Fore.GREEN}"
        f"Status  :  Applied successfully"
        f"{Style.RESET_ALL}"
        f"{ts}"
    )


def print_status_skipped_external() -> None:
    # External apply jobs cannot be submitted via the API. The URL is printed
    # in the job header so the user can open it manually if needed.
    print(
        f"  {Fore.YELLOW}"
        f"Status  :  Skipped — external apply "
        f"(open URL manually)"
        f"{Style.RESET_ALL}"
    )


def print_status_failed(
    error,
) -> None:
    print(f"  {Fore.RED}" f"Status  :  Failed — {error}" f"{Style.RESET_ALL}")


def print_status_manual_review(error) -> None:
    print(
        f"  {Fore.YELLOW}"
        f"Status  :  Manual review required — {error}"
        f"{Style.RESET_ALL}"
    )


def print_questionnaire_notice() -> None:
    print(
        f"  {Fore.CYAN}"
        f"           Questionnaire detected, "
        f"handling automatically"
        f"{Style.RESET_ALL}"
    )


def print_pipeline_results(
    final_jobs: list,
) -> None:
    # Prints a compact ranked table of every job that passed the AI filter,
    # sorted by score descending. Gives a quick overview before the apply loop.
    print_section_title(f"AI filter — {len(final_jobs)} jobs passed")

    col_w = [
        4,
        35,
        28,
        6,
    ]

    header = (
        f"  {Fore.WHITE}"
        f"{'#':<{col_w[0]}}  "
        f"{'Title':<{col_w[1]}}  "
        f"{'Company':<{col_w[2]}}  "
        f"{'Score':>{col_w[3]}}"
        f"{Style.RESET_ALL}"
    )

    print(header)

    print(f"  {Fore.WHITE}" f"{'─' * sum(col_w)}" f"{Style.RESET_ALL}")

    for index, job in enumerate(
        final_jobs,
        1,
    ):
        score = job.get(
            "ai_score",
            job.get("score", "?"),
        )

        score_color = (
            Fore.GREEN
            if score and score >= 70
            else (Fore.YELLOW if score and score >= 50 else Fore.RED)
        )

        score_display = (
            f"{score_color}" f"{score:>3}" f"{Style.RESET_ALL}"
            if score is not None
            else "  ?"
        )

        title = (job.get("title") or "")[: col_w[1]]

        company = (job.get("company") or "")[: col_w[2]]

        print(
            f"  {Fore.CYAN}"
            f"{index:<{col_w[0]}}"
            f"{Style.RESET_ALL}  "
            f"{title:<{col_w[1]}}  "
            f"{Fore.YELLOW}"
            f"{company:<{col_w[2]}}"
            f"{Style.RESET_ALL}  "
            f"{score_display}"
        )


def print_fetch_progress(
    keyword: str,
    location: str,
    exp: int,
    page: int,
    fetched: int,
    new: int,
) -> None:
    # Prints a single progress line per search query showing how many jobs
    # were returned and how many were new (not seen in earlier queries).
    loc = location or "All India"

    kw_display = keyword[:30].ljust(30)
    loc_display = loc[:12].ljust(12)

    new_color = Fore.GREEN if new > 0 else Fore.WHITE

    print(
        f"  {Fore.WHITE}"
        f"[{kw_display} | "
        f"{loc_display} | "
        f"exp={exp} | "
        f"p{page}]"
        f"{Style.RESET_ALL}"
        f"  {Fore.WHITE}"
        f"{fetched:>3} fetched  "
        f"{new_color}"
        f"{new:>3} new"
        f"{Style.RESET_ALL}"
    )


def print_summary(
    total_found: int,
    total_allowed: int,
    applied: int,
    already_applied: int,
    skipped_local: int,
    skipped_ext: int,
    policy_rejected: int,
    dry_run_skipped: int,
    run_limit_reached: int,
    failed: int,
) -> None:
    """
    Print the final deterministic application run summary.
    """

    print_section_title("run summary")

    rows = [
        (
            "Jobs fetched (total unique)",
            str(total_found),
            Fore.WHITE,
        ),
        (
            "Jobs passed AI filter",
            str(total_allowed),
            Fore.CYAN,
        ),
        (
            "Applied successfully",
            str(applied),
            Fore.GREEN,
        ),
        (
            "Already applied (server)",
            str(already_applied),
            Fore.CYAN,
        ),
        (
            "Skipped (local history)",
            str(skipped_local),
            Fore.WHITE,
        ),
        (
            "Skipped (external apply)",
            str(skipped_ext),
            Fore.YELLOW,
        ),
        (
            "Rejected by policy",
            str(policy_rejected),
            Fore.YELLOW,
        ),
        (
            "Suppressed by dry run",
            str(dry_run_skipped),
            Fore.CYAN,
        ),
        (
            "Skipped (run limit)",
            str(run_limit_reached),
            Fore.YELLOW,
        ),
        (
            "Failed",
            str(failed),
            Fore.RED,
        ),
    ]

    for label, value, color in rows:
        print(
            f"  {Fore.WHITE}"
            f"{label:<30}"
            f"{Style.RESET_ALL}  "
            f"{color}"
            f"{Style.BRIGHT}"
            f"{value}"
            f"{Style.RESET_ALL}"
        )

    print(LINE + "\n")


# ----------------------------------------------------------------------------------
# Job fetching
#
# Runs a fixed set of search queries against the Naukri search API and
# collects results into a deduplicated list.
#
# Design decisions:
#   - Queries are hand-curated for the target stack (Node.js, Python, backend).
#   - Only Bangalore and Pune are targeted — highest product/startup density.
#   - Experience is fixed at 2 years. exp=3 pulled in too many senior roles.
#   - job_age=2 keeps results fresh, which improves apply response rates.
#   - 1 page per query. Quality drops sharply beyond page 2 on Naukri.
#   - 1.2s sleep between requests to avoid rate limiting.
#   - Deduplication is done by job_id across all queries before returning.
# ----------------------------------------------------------------------------------


@dataclass
class JobFetchResult:
    jobs: list
    challenge_encountered: bool = False
    completed_normally: bool = True
    search_skipped_due_to_cooldown: bool = False
    search_requests_attempted: int = 0
    pages_stopped_low_yield: int = 0
    stop_reasons: dict[str, int] = field(default_factory=dict)
    jobspy_health: dict = field(default_factory=dict)


def fetch_all_jobs(
    jc: NaukriJobClient,
    *,
    mode: str = "full",
) -> JobFetchResult:

    # Generate queries from configuration
    planner = SearchPlanner()
    SEARCH_TRACKS = planner.generate_queries()

    if not SEARCH_TRACKS:
        raise ValueError(
            "SearchPlanner generated 0 queries. Check config/user_profile.yaml"
        )

    def _env_int_list(name: str, default: str) -> list[int]:
        raw = os.getenv(name, default)
        values: list[int] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            value = int(part)
            if value < 0:
                raise ValueError(f"{name} values must be non-negative")
            if value not in values:
                values.append(value)
        if not values:
            raise ValueError(f"{name} must contain at least one integer")
        return values

    if mode not in {"full", "incremental"}:
        raise ValueError("mode must be 'full' or 'incremental'")
    default_exp = "2,4,6,8" if mode == "full" else "4,6"
    EXPERIENCE_LEVELS = _env_int_list("SEARCH_EXPERIENCE_LEVELS", default_exp)
    default_pages = "3" if mode == "full" else "1"
    PAGES = int(os.getenv("SEARCH_MAX_PAGES", default_pages))
    JOB_AGE = int(os.getenv("SEARCH_JOB_AGE_DAYS", "3"))
    RESULTS_PER_PAGE = int(os.getenv("SEARCH_RESULTS_PER_PAGE", "20"))

    if PAGES < 1:
        raise ValueError("SEARCH_MAX_PAGES must be at least 1")
    if JOB_AGE < 0:
        raise ValueError("SEARCH_JOB_AGE_DAYS must be non-negative")
    if RESULTS_PER_PAGE < 1:
        raise ValueError("SEARCH_RESULTS_PER_PAGE must be at least 1")

    seen_ids: set[str] = set()
    all_jobs = []

    challenge_encountered = False
    search_requests_attempted = 0
    pages_stopped_low_yield = 0
    stop_reasons: dict[str, int] = {}
    min_new_yield = int(os.getenv("SEARCH_MIN_NEW_JOBS_PER_PAGE", "2"))
    low_yield_patience = int(os.getenv("SEARCH_LOW_YIELD_PATIENCE", "1"))

    print_section_title(
        f"fetching jobs  "
        f"({len(SEARCH_TRACKS)} queries x "
        f"{len(EXPERIENCE_LEVELS)} exp x "
        f"{PAGES} page)"
    )

    for query in SEARCH_TRACKS:
        if challenge_encountered:
            break

        for exp in EXPERIENCE_LEVELS:
            if challenge_encountered:
                break

            previous_page_signature: tuple[str, ...] | None = None
            consecutive_low_yield = 0

            for page in range(1, PAGES + 1):
                try:
                    search_requests_attempted += 1

                    jobs = jc.search_jobs(
                        keyword=query["keyword"],
                        location=query["location"],
                        experience=exp,
                        job_age=JOB_AGE,
                        page=page,
                        results_per_page=RESULTS_PER_PAGE,
                    )

                    page_signature = tuple(
                        str(
                            getattr(job, "id", None)
                            or getattr(job, "job_id", None)
                            or ""
                        )
                        for job in jobs
                    )

                    if jobs and page_signature == previous_page_signature:
                        print_fetch_progress(
                            query["keyword"],
                            query["location"],
                            exp,
                            page,
                            fetched=len(jobs),
                            new=0,
                        )
                        break

                    previous_page_signature = page_signature
                    new_jobs = []

                    for job in jobs:
                        job_id = getattr(
                            job,
                            "id",
                            None,
                        ) or getattr(
                            job,
                            "job_id",
                            None,
                        )

                        if job_id and job_id in seen_ids:
                            continue

                        if job_id:
                            seen_ids.add(job_id)

                        setattr(
                            job,
                            "search_track",
                            query["track"],
                        )

                        setattr(
                            job,
                            "search_query",
                            query["keyword"],
                        )

                        setattr(
                            job,
                            "search_profile",
                            query.get("search_profile", "unknown"),
                        )

                        setattr(
                            job,
                            "matched_technology",
                            query.get("matched_technology", ""),
                        )

                        setattr(
                            job,
                            "acquisition_source",
                            "live",
                        )

                        new_jobs.append(job)

                    all_jobs.extend(new_jobs)

                    print_fetch_progress(
                        query["keyword"],
                        query["location"],
                        exp,
                        page,
                        fetched=len(jobs),
                        new=len(new_jobs),
                    )

                    if not jobs or len(jobs) < RESULTS_PER_PAGE:
                        stop_reasons["short_page"] = (
                            stop_reasons.get("short_page", 0) + 1
                        )
                        break

                    if len(new_jobs) < min_new_yield:
                        consecutive_low_yield += 1
                    else:
                        consecutive_low_yield = 0
                    if page < PAGES and consecutive_low_yield >= low_yield_patience:
                        pages_stopped_low_yield += 1
                        stop_reasons["low_yield"] = stop_reasons.get("low_yield", 0) + 1
                        break

                    time.sleep(float(os.getenv("SEARCH_REQUEST_DELAY_SECONDS", "1.2")))

                except NaukriSearchChallengeError as exc:
                    challenge_encountered = True

                    print(
                        f"\n  {Fore.YELLOW}"
                        f"[SEARCH STOPPED]"
                        f"{Style.RESET_ALL}  "
                        f"{exc}. Continuing with "
                        f"{len(all_jobs)} collected jobs."
                    )

                    break

                except Exception as exc:
                    print(
                        f"  {Fore.RED}"
                        f"[FAIL]"
                        f"{Style.RESET_ALL}  "
                        f"{query['keyword']} @ "
                        f"{query['location']}  "
                        f"exp={exp} p={page}  ->  "
                        f"{exc}"
                    )

                    time.sleep(3)

    print(
        f"\n  {Fore.CYAN}"
        f"Total unique jobs collected: "
        f"{Style.BRIGHT}"
        f"{len(all_jobs)}"
        f"{Style.RESET_ALL}"
    )

    return JobFetchResult(
        jobs=all_jobs,
        challenge_encountered=challenge_encountered,
        completed_normally=not challenge_encountered,
        search_requests_attempted=search_requests_attempted,
        pages_stopped_low_yield=pages_stopped_low_yield,
        stop_reasons=stop_reasons,
    )


def resolve_job_acquisition(
    fetch_result: JobFetchResult,
    cache: JobSearchCache,
) -> list:
    """
    Resolve final jobs from live acquisition and fresh cache entries.

    Policy:
        - normal search:
            use live results only and refresh cache

        - partial challenged search:
            merge live jobs with fresh cache jobs

        - challenge before acquisition:
            use fresh cache jobs

        - cooldown-suppressed search:
            use fresh cache jobs

    Provenance:
        live        -> observed only in current search
        cache       -> recovered only from cache
        live+cache  -> observed in both
    """

    fresh_jobs = fetch_result.jobs
    cached_jobs = cache.load()

    fresh_ids = {
        job.job_id
        for job in fresh_jobs
        if getattr(
            job,
            "job_id",
            None,
        )
    }

    cached_ids = {
        job.job_id
        for job in cached_jobs
        if getattr(
            job,
            "job_id",
            None,
        )
    }

    for job in fresh_jobs:
        job_id = getattr(
            job,
            "job_id",
            None,
        )

        source = "live+cache" if job_id in cached_ids else "live"

        setattr(
            job,
            "acquisition_source",
            source,
        )

    for job in cached_jobs:
        job_id = getattr(
            job,
            "job_id",
            None,
        )

        source = "live+cache" if job_id in fresh_ids else "cache"

        setattr(
            job,
            "acquisition_source",
            source,
        )

    if fetch_result.search_skipped_due_to_cooldown:
        if cached_jobs:
            print(
                f"\n  {Fore.YELLOW}"
                f"Live search suppressed by challenge cooldown."
                f"{Style.RESET_ALL}"
                f"\n  Using {len(cached_jobs)} cached jobs."
            )

        return cached_jobs

    if fetch_result.challenge_encountered:
        if fresh_jobs:
            merged_jobs = cache.merge(
                fresh_jobs=fresh_jobs,
                cached_jobs=cached_jobs,
            )

            for job in merged_jobs:
                job_id = getattr(
                    job,
                    "job_id",
                    None,
                )

                if job_id in fresh_ids and job_id in cached_ids:
                    source = "live+cache"

                elif job_id in fresh_ids:
                    source = "live"

                else:
                    source = "cache"

                setattr(
                    job,
                    "acquisition_source",
                    source,
                )

            cache.save(merged_jobs)

            print(
                f"\n  {Fore.YELLOW}"
                f"Search challenge encountered after partial acquisition."
                f"{Style.RESET_ALL}"
                f"\n  Fresh jobs  : {len(fresh_jobs)}"
                f"\n  Cached jobs : {len(cached_jobs)}"
                f"\n  Final jobs  : {len(merged_jobs)}"
            )

            return merged_jobs

        if cached_jobs:
            print(
                f"\n  {Fore.YELLOW}"
                f"Search challenge encountered before fresh acquisition."
                f"{Style.RESET_ALL}"
                f"\n  Using {len(cached_jobs)} cached jobs."
            )

            return cached_jobs

        return []

    cache.save(fresh_jobs)

    return fresh_jobs


def acquire_jobs(
    providers: dict,
    cache: JobSearchCache,
    cooldown: SearchChallengeCooldown,
    mode: str = "full",
    force_live: bool = False,
) -> tuple[list, JobFetchResult]:
    """
    Execute cooldown-aware job acquisition.

    Naukri acquisition is unchanged. If JobSpy is enabled in
    config/search_strategy.yaml, its results are fetched independently
    and merged into the final list.

    Naukri CAPTCHA cooldown suppresses only live Naukri searches.
    JobSpy acquisition continues to run so providers remain isolated.
    """

    # Load configuration to get provider_priority
    acq_config = load_acquisition_config()

    run_naukri = "naukri" in providers
    run_jobspy = "jobspy" in providers

    print("Entered acquire_jobs()")
    print(f"Running Naukri = {run_naukri}")
    print(f"Running JobSpy = {run_jobspy}")

    # ---------------------------------------------------------------
    # Acquire Naukri jobs (live or cache)
    # ---------------------------------------------------------------
    if not run_naukri:
        naukri_jobs = []
        fetch_result = JobFetchResult(
            jobs=[],
            challenge_encountered=False,
            completed_normally=True,
        )
    else:
        jc = providers["naukri"]
        if not force_live and cooldown.is_active():
            fetch_result = JobFetchResult(
                jobs=[],
                challenge_encountered=False,
                completed_normally=False,
                search_skipped_due_to_cooldown=True,
                search_requests_attempted=0,
            )

            naukri_jobs = resolve_job_acquisition(
                fetch_result=fetch_result,
                cache=cache,
            )

        else:
            print(">>> RUNNING NAUKRI ACQUISITION")
            fetch_result = (
                fetch_all_jobs(jc) if mode == "full" else fetch_all_jobs(jc, mode=mode)
            )

            if fetch_result.challenge_encountered:
                cooldown.record_challenge()

            naukri_jobs = resolve_job_acquisition(
                fetch_result=fetch_result,
                cache=cache,
            )

    for job in naukri_jobs:
        setattr(job, "provider_id", "naukri")

    # ---------------------------------------------------------------
    # JobSpy additive acquisition
    #
    # Note: Does not mutate fetch_result since JobSpy does not run under
    # the Naukri challenge constraints.
    #
    # Failure of JobSpy never affects Naukri.
    # ---------------------------------------------------------------

    jobspy_jobs = []
    if not run_jobspy:
        print("Skipping JobSpy acquisition (disabled or not initialized).")
    else:
        jobspy_provider = providers["jobspy"]

        # Reuse identical search queries generated for Naukri.
        planner = SearchPlanner()
        search_tracks = planner.generate_queries()
        print("Calling fetch_jobspy_jobs()")
        jobspy_jobs = fetch_jobspy_jobs(
            provider=jobspy_provider,
            search_tracks=search_tracks,
        )
        print(f"JobSpy returned {len(jobspy_jobs)} jobs")
        jobspy_queries = sum(
            h.get("total_searches", 0)
            for h in jobspy_provider.health_summary().values()
        )
        fetch_result.search_requests_attempted += jobspy_queries

        health_summary = {}
        degraded = getattr(jobspy_provider, "degraded_providers", set())
        for site, h in jobspy_provider.health_summary().items():
            site_status = "degraded" if site in degraded else "active"
            health_summary[site] = {"status": site_status, **h}
        fetch_result.jobspy_health = health_summary

    for job in jobspy_jobs:
        setattr(job, "provider_id", "jobspy")

    provider_priority = acq_config.get(
        "provider_priority",
        ["naukri", "indeed", "linkedin", "google"],
    )

    jobs = merge_jobs(
        naukri_jobs=naukri_jobs,
        jobspy_jobs=jobspy_jobs,
        provider_priority=provider_priority,
    )

    print(f"Merged {len(jobs)} jobs")

    logger.info(
        "Acquisition merge: naukri=%d jobspy=%d merged=%d",
        len(naukri_jobs),
        len(jobspy_jobs),
        len(jobs),
    )

    return jobs, fetch_result


# ----------------------------------------------------------------------------------
# Questionnaire resolution
# ----------------------------------------------------------------------------------


class QuestionnaireResolver(Protocol):
    """
    Structural interface required by resolve_questionnaire().

    HybridQuestionResolver and test doubles can both satisfy this protocol
    without inheritance or concrete-type coupling.
    """

    def resolve(
        self,
        question: dict,
        profile: dict,
    ) -> Any: ...


def resolve_questionnaire(
    resolver: QuestionnaireResolver,
    questionnaire: list[dict],
    profile: dict,
) -> tuple[
    dict[str, object],
    list[dict],
]:
    """
    Resolve every questionnaire item through the supplied resolver.

    Resolved answers are returned in submission-ready serialized form.
    Questions that cannot be safely resolved are returned separately for
    telemetry and manual review.
    """
    answers: dict[str, object] = {}
    unresolved: list[dict] = []

    for question in questionnaire:
        resolution = resolver.resolve(
            question=question,
            profile=profile,
        )

        question_id = str(question.get("questionId") or "").strip()

        if (
            resolution.resolved
            and resolution.serialized_answer is not None
            and question_id
        ):
            answers[question_id] = resolution.serialized_answer

            continue

        unresolved.append(
            {
                **question,
                "resolution_status": resolution.status,
                "resolution_source": resolution.source,
                "resolution_confidence": resolution.confidence,
                "resolution_reasoning": resolution.reasoning,
            }
        )

    return answers, unresolved


class JobProvider(Protocol):
    """
    Structural interface required by downstream pipeline stages.

    Providers (e.g. NaukriJobClient) and test doubles can satisfy this protocol
    without inheritance or concrete-type coupling.
    """

    def get_job_details(self, job_id: str) -> dict | None: ...

    def is_external_apply(self, job_id: str) -> bool: ...

    def reconcile_history(self, ledger: Any) -> dict | None: ...

    def apply_job(
        self,
        job: Any,
        mandatory_skills: list[str] | None = None,
        optional_skills: list[str] | None = None,
        sid: str = "",
        source: str = "recommended",
    ) -> dict: ...

    def submit_questionnaire_answers(
        self,
        job: Any,
        answers: dict[str, object],
        sid: str,
        source: str = "search",
    ) -> dict: ...


class ManualReviewRequired(RuntimeError):
    """Application paused because questionnaire answers require human review."""


@dataclass(frozen=True)
class ApplicationRunSummary:
    total_candidates: int
    applied: int
    already_applied: int
    skipped_local: int
    native_applied: int
    ats_queue: int
    generic_queue: int
    manual_queue: int
    unsupported: int
    policy_rejected: int
    dry_run_skipped: int
    run_limit_reached: int
    failed: int
    manual_review: int
    applied_jobs: list = field(default_factory=list)


def execute_with_safe_retry(
    operation,
    *,
    max_retries: int = 2,
    sleep_fn=time.sleep,
):
    """
    Execute an application operation with bounded retry.

    Only failures classified as RETRYABLE_SAFE are retried.
    Ambiguous and permanent failures are raised immediately.

    max_retries counts retries after the initial attempt.
    Therefore max_retries=2 allows at most 3 total attempts.
    """

    retries_used = 0

    while True:
        try:
            return operation()

        except Exception as exc:
            failure = classify_application_exception(exc)

            if failure.kind != FailureKind.RETRYABLE_SAFE:
                raise

            if retries_used >= max_retries:
                raise

            retries_used += 1

            delay_seconds = retries_used

            logger.warning(
                "Retryable application failure. " "retry=%s/%s delay=%ss reason=%s",
                retries_used,
                max_retries,
                delay_seconds,
                failure.reason,
            )

            sleep_fn(delay_seconds)


def process_job_application(
    jc: JobProvider,
    job: Any,
    meta: dict,
    questionnaire_resolver: QuestionnaireResolver,
) -> ApplicationOutcome:
    """
    Execute the complete application workflow for one job.

    Responsibilities:
        1. Submit the initial application.
        2. Interpret the initial API response.
        3. Return immediately for direct success or already-applied outcomes.
        4. Resolve and submit questionnaires when required.
        5. Log unresolved questionnaire items before failing safely.
        6. Interpret and return the final questionnaire submission outcome.

    This function does not:
        - print terminal status
        - update counters
        - persist applied jobs
        - sleep between applications

    Those responsibilities remain with the outer orchestration loop.
    """

    mandatory = job.tags[:2] if job.tags else []
    optional = job.tags[2:] if len(job.tags) > 2 else []

    initial_response = execute_with_safe_retry(
        lambda: jc.apply_job(
            job,
            mandatory_skills=mandatory,
            optional_skills=optional,
            source="search",
        ),
    )

    save_response(
        job_id=job.job_id,
        stage="initial_apply_raw",
        response=initial_response,
    )

    initial_outcome = interpret_application_response(
        job_id=job.job_id,
        response=initial_response,
    )

    if initial_outcome.status in {
        ApplicationStatus.APPLIED,
        ApplicationStatus.ALREADY_APPLIED,
    }:
        return initial_outcome

    if initial_outcome.status != ApplicationStatus.QUESTIONNAIRE_REQUIRED:
        return initial_outcome

    questionnaire = initial_outcome.questionnaire

    answers, unresolved = resolve_questionnaire(
        resolver=questionnaire_resolver,
        questionnaire=questionnaire,
        profile=CANDIDATE_PROFILE,
    )

    if unresolved:
        log_unresolved_questions(
            row={
                "job_id": job.job_id,
                "title": job.title,
                "company": job.company,
                "priority": meta.get("priority", ""),
                "subtrack": meta.get("subtrack", ""),
            },
            questions=unresolved,
        )

        raise ManualReviewRequired(
            "Questionnaire requires manual review: "
            f"{len(unresolved)} unresolved question(s)"
        )

    sid = datetime.now(UTC).strftime("%Y%m%d%H%M%S") + "0000000"

    final_response = jc.submit_questionnaire_answers(
        job=job,
        answers=answers,
        sid=sid,
        source="search",
    )

    save_response(
        job_id=job.job_id,
        stage="questionnaire_submit_raw",
        response=final_response,
    )

    return interpret_application_response(
        job_id=job.job_id,
        response=final_response,
    )


def _extract_job_detail_description(detail: dict) -> str:
    """
    Extract and normalize the full JD from the Naukri detail payload.

    The client intentionally returns raw JSON, so extraction remains outside
    the transport layer.
    """

    job_data = detail.get("job") or {}

    raw_description = (
        job_data.get("jobDescription")
        or job_data.get("description")
        or detail.get("jobDescription")
        or detail.get("description")
        or ""
    )

    if not isinstance(raw_description, str):
        return ""

    text = html.unescape(raw_description)

    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"</p\s*>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n\s*\n+",
        "\n\n",
        text,
    )

    return text.strip()


def enrich_jobs_with_details(
    providers: dict,
    jobs: list[dict],
    detail_cache: dict[str, dict] | None = None,
    cache_manager: CacheManager | None = None,
) -> list[dict]:
    """
    Fetch each candidate's detail payload once and enrich the normalized
    classifier job with its full description.

    JobSpy jobs (job_id starting with "jobspy_") are skipped for Naukri
    detail enrichment because they use a different provider and the Naukri
    detail API will simply 404 on their IDs.  They retain whatever
    description the JobSpy adapter already extracted.

    Failed detail fetches are retained with their existing search-result
    description rather than silently deleting potentially valid candidates.
    """

    enriched_jobs = []

    for index, job in enumerate(
        jobs,
        start=1,
    ):
        job_id = str(job.get("job_id") or "").strip()

        if not job_id:
            enriched_jobs.append(job)
            continue

        if job_id.startswith("jobspy_"):
            enriched_jobs.append(job)
            continue

        provider_id = job.get("provider_id", "naukri")
        provider = providers.get(provider_id)

        if not provider:
            enriched_jobs.append(job)
            continue

        print(
            f"  [DETAIL {index}/{len(jobs)}] "
            f"{job.get('title')} @ "
            f"{job.get('company')}"
        )

        try:
            detail = None
            fingerprint = None
            
            if cache_manager:
                fingerprint = compute_detail_fetch_fingerprint(provider_id, job_id, "")
                start_time = time.perf_counter()
                record = cache_manager.detail.get(fingerprint)
                cache_manager.track_lookup((time.perf_counter() - start_time) * 1000)
                
                if record:
                    import json
                    try:
                        detail = json.loads(record["content"])
                        cache_manager.metrics["detail_hits"] += 1
                    except json.JSONDecodeError:
                        pass
                else:
                    cache_manager.metrics["detail_misses"] += 1
            elif detail_cache is not None:
                detail = detail_cache.get(job_id)

            if detail is None:
                detail = provider.get_job_details(job_id)
                if detail:
                    if cache_manager and fingerprint:
                        import json
                        start_time = time.perf_counter()
                        cache_manager.detail.set(
                            fingerprint=fingerprint,
                            provider=provider_id,
                            job_id=job_id,
                            content=json.dumps(detail)
                        )
                        cache_manager.track_save((time.perf_counter() - start_time) * 1000)
                    elif detail_cache is not None:
                        detail_cache[job_id] = detail

            full_description = _extract_job_detail_description(detail)

            if full_description:
                job["description"] = full_description

            job_data = detail.get("job") or {}

            # Preserve richer location/work-mode evidence for the eligibility gate.
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

            job["is_external_apply"] = job_data.get("responseManager") == "companyUrl"

            enriched_jobs.append(job)

        except Exception as exc:
            logger.warning(
                "Job detail enrichment failed: " "job_id=%s error=%s",
                job_id,
                exc,
            )

            job["detail_enrichment_failed"] = True

            enriched_jobs.append(job)

    return enriched_jobs


def run_application_batch(
    providers: dict,
    jobs: list,
    score_map: dict,
    questionnaire_resolver: QuestionnaireResolver | None,
    applied_jobs_set: set[str],
    policy: ApplicationPolicy | None = None,
    detail_cache: dict[str, dict] | None = None,
    sleep_fn=time.sleep,
    ledger: ApplicationLedger | None = None,
    run_id: str = "",
    metrics: PipelineRunMetrics | None = None,
    rejected_jobs: list | None = None,
    exec_context=None,
) -> ApplicationRunSummary:
    """
    Execute the application workflow for a batch of filtered jobs.

    Enforcement order:

        1. local idempotency
        2. static application policy
        3. dry-run boundary
        4. external application check
        5. application execution
        6. persistence reconciliation

    A policy-rejected or dry-run job can never reach
    process_job_application().
    """

    effective_policy = policy or ApplicationPolicy(
        dry_run=False,
    )

    applied_count = 0
    applied_jobs_list = []
    already_applied_count = 0
    skipped_local_count = 0
    native_applied_count = 0
    ats_queue_count = 0
    generic_queue_count = 0
    manual_queue_count = 0
    unsupported_count = 0
    policy_rejected_count = 0
    dry_run_skipped_count = 0
    run_limit_reached_count = 0
    failed_count = 0
    manual_review_count = 0
    detail_cache = detail_cache or {}

    successful_submissions = 0
    breaker = CircuitBreaker(
        max_consecutive_failures=int(
            os.getenv("APPLICATION_MAX_CONSECUTIVE_FAILURES", "5")
        )
    )

    total_candidates = len(jobs)
    rejected_jobs_list = rejected_jobs if rejected_jobs is not None else []

    def _record_app_reject(job, code, reason):
        from datetime import datetime, timezone

        rejected_jobs_list.append(
            {
                "job_id": str(getattr(job, "job_id", "")),
                "title": str(getattr(job, "title", "Unknown")),
                "company": str(getattr(job, "company", "Unknown")),
                "stage": "Application",
                "code": code,
                "reason": str(reason),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    manual_action_queue = ManualActionQueue(
        os.getenv(
            "MANUAL_ACTION_QUEUE_PATH",
            "data/manual_action_queue.json",
        )
    )

    if exec_context:
        exec_context.start_stage("Application", jobs)

    print(f"\n--- Starting application batch ({len(jobs)} jobs) ---")

    for index, job in enumerate(
        jobs,
        start=1,
    ):
        meta = score_map.get(
            job.job_id,
            {},
        )

        if ledger is not None:
            ledger.record(job, "qualified", meta=meta)

        score = meta.get("score")
        ai_detail = meta.get("ai_detail")

        print_job_header(
            index=index,
            total=total_candidates,
            job=job,
            score=score,
            ai_detail=ai_detail,
        )

        # ----------------------------------------------------------
        # Local idempotency
        # ----------------------------------------------------------

        if job.job_id in applied_jobs_set:
            logger.info(
                "Skipping locally persisted job: job_id=%s",
                job.job_id,
            )

            already_applied_count += 1
            _record_app_reject(
                job, "ALREADY_APPLIED", "Previously applied in an earlier run."
            )
            if ledger is not None:
                ledger.record(job, "already_applied", meta=meta)

            if exec_context:
                exec_context.reject(
                    job,
                    reason="Previously applied in an earlier run.",
                    code="ALREADY_APPLIED",
                )
            continue

        # ----------------------------------------------------------
        # Static application policy
        # ----------------------------------------------------------

        policy_evaluation = evaluate_application_policy(
            meta=meta,
            policy=effective_policy,
        )

        if not policy_evaluation.allowed:
            logger.info(
                "Policy rejected job_id=%s reason=%s detail=%s",
                job.job_id,
                policy_evaluation.reason.value,
                policy_evaluation.detail,
            )

            policy_rejected_count += 1
            _record_app_reject(
                job, policy_evaluation.reason.value, policy_evaluation.detail
            )
            
            if exec_context:
                exec_context.reject(
                    job,
                    reason=policy_evaluation.detail,
                    code=policy_evaluation.reason.value,
                )
                
            if ledger is not None:
                ledger.record(
                    job,
                    "policy_rejected",
                    meta=meta,
                    detail=policy_evaluation.reason.value,
                )
            continue

        # ----------------------------------------------------------
        # Per-run application limit (same candidate prefix in dry/live)
        # ----------------------------------------------------------

        if (
            effective_policy.max_applications_per_run is not None
            and successful_submissions >= effective_policy.max_applications_per_run
        ):
            run_limit_reached_count = total_candidates - index + 1
            logger.info(
                "Per-run successful submission limit reached. "
                "Leaving %s queued candidate(s) for a later run.",
                run_limit_reached_count,
            )
            for remaining_job in jobs[index - 1 :]:
                _record_app_reject(
                    remaining_job,
                    "APPLICATION_QUOTA",
                    "Per-run successful submission limit reached",
                )
                if exec_context:
                    exec_context.reject(
                        remaining_job,
                        "Per-run successful submission limit reached",
                        "APPLICATION_QUOTA",
                    )
            break

        if effective_policy.dry_run:
            logger.info("Dry-run: application suppressed for job_id=%s", job.job_id)
            print(
                f"  [{index}/{len(jobs)}] Skipping dry-run: {job.title} @ {job.company}"
            )
            dry_run_skipped_count += 1
            if exec_context:
                exec_context.skip(job, reason="Dry run mode is enabled", code="DRY_RUN")
            if ledger is not None:
                ledger.record(job, "dry_run_suppressed", meta=meta)
            continue

        # ----------------------------------------------------------
        # Application Routing Engine
        # ----------------------------------------------------------

        try:
            provider_id = getattr(job, "provider_id", "naukri")
            jc = providers.get(provider_id)

            if not jc:
                raise ValueError(
                    f"Provider '{provider_id}' is not configured "
                    "in providers dictionary"
                )

            is_external = meta.get("is_external_apply")
            if is_external is None:
                is_external = jc.is_external_apply(job.job_id)

            capabilities = ProviderCapabilities(
                native_apply=not is_external,  # Naukri natively supports it, but this job might be external
                returns_external_url=True,
                requires_authentication=True,
                supports_resume_upload=True,
                supports_questionnaires=True,
            )

            external_url = getattr(job, "apply_link", None) if is_external else None

            route_result = ApplicationRouter.route(job, capabilities, external_url)

            if route_result.strategy != RoutingStrategy.NATIVE_APPLY:
                if route_result.strategy == RoutingStrategy.EXTERNAL_ATS:
                    ats_queue_count += 1
                elif route_result.strategy == RoutingStrategy.GENERIC_CAREER_SITE:
                    generic_queue_count += 1
                elif route_result.strategy == RoutingStrategy.MANUAL_REVIEW:
                    manual_queue_count += 1
                elif route_result.strategy == RoutingStrategy.UNSUPPORTED:
                    unsupported_count += 1

                _record_app_reject(
                    job, route_result.strategy.name, route_result.reasoning
                )
                if exec_context:
                    exec_context.route(
                        job,
                        strategy=route_result.strategy.name,
                        reason=route_result.reasoning,
                    )
                if ledger is not None:
                    ledger.record(job, route_result.strategy.name.lower(), meta=meta)

                # enqueue for manual review or future queue workers
                job_id = str(job.job_id)
                score_result = score_map.get(job_id, {})
                manual_action_queue.enqueue_external_apply(
                    job=job,
                    score=int(
                        score_result.get("score", score_result.get("ai_score", 0)) or 0
                    ),
                    reason=str(
                        score_result.get("ai_detail", score_result.get("ai_reason", ""))
                        or ""
                    ),
                    run_id=run_id,
                )
                continue

        except Exception as exc:
            print_status_failed(exc)

            failed_count += 1
            if exec_context:
                exec_context.fail(job, str(exc))
            if ledger is not None:
                ledger.record(job, "detail_check_failed", meta=meta, error=str(exc))
            continue

        # ----------------------------------------------------------
        # Application execution
        # ----------------------------------------------------------

        try:
            if ledger is not None:
                ledger.record(job, "applying", meta=meta)

            if questionnaire_resolver is None:
                raise RuntimeError(
                    "Questionnaire resolver is required for live application execution"
                )

            start_time = time.perf_counter()
            outcome = process_job_application(
                jc=jc,
                job=job,
                meta=meta,
                questionnaire_resolver=questionnaire_resolver,
            )
            duration = time.perf_counter() - start_time
            if metrics:
                metrics.add_application_time(duration)

            if outcome.status == ApplicationStatus.ALREADY_APPLIED:
                logger.info(
                    "Server reports job already applied: job_id=%s",
                    job.job_id,
                )

                applied_jobs_set.add(job.job_id)

                already_applied_count += 1
                _record_app_reject(
                    job, "ALREADY_APPLIED", "Server reports job already applied"
                )
                if exec_context:
                    exec_context.reject(
                        job,
                        reason="Server reports job already applied",
                        code="ALREADY_APPLIED",
                    )

                if ledger is not None:
                    ledger.record(job, "already_applied", meta=meta)

                continue

            if outcome.status != ApplicationStatus.APPLIED:
                raise RuntimeError(
                    "Application did not produce a successful outcome: "
                    f"{outcome.status.value}. "
                    f"{outcome.reasoning}"
                )

            applied_at = datetime.now(UTC).strftime("%H:%M:%S UTC")

            print_status_applied(applied_at)

            applied_jobs_set.add(job.job_id)

            applied_count += 1
            applied_jobs_list.append(job)
            successful_submissions += 1
            breaker.success()

            if exec_context:
                exec_context.apply(
                    job,
                    outcome="Applied",
                    explanation={"cause": "Successfully processed application"},
                )

            if ledger is not None:
                ledger.record(job, "applied", meta=meta)

        except ManualReviewRequired as exc:
            print_status_manual_review(exc)
            manual_review_count += 1
            _record_app_reject(job, "MANUAL_REVIEW", str(exc))
            if exec_context:
                exec_context.route(job, strategy="MANUAL_REVIEW", reason=str(exc))
            breaker.success()

            if ledger is not None:
                ledger.record(
                    job,
                    "manual_review",
                    meta=meta,
                    error=str(exc),
                )

            manual_action_queue.enqueue_manual_review(
                job=job,
                score=int(
                    meta.get(
                        "score",
                        meta.get(
                            "ai_score",
                            0,
                        ),
                    )
                    or 0
                ),
                reason=str(exc),
                run_id=run_id,
            )

        except Exception as exc:
            print_status_failed(exc)

            failed_count += 1

            if ledger is not None:
                failure = classify_application_exception(exc)
                status = (
                    "retryable_failure"
                    if failure.kind == FailureKind.RETRYABLE_SAFE
                    else "permanent_failure"
                )
                ledger.record(job, status, meta=meta, error=str(exc))

            if breaker.failure(f"{type(exc).__name__}: {exc}"):
                raise RuntimeError(
                    f"Application circuit breaker tripped after {breaker.consecutive_failures} consecutive failures: {breaker.reason}"
                ) from exc

        finally:
            sleep_fn(3)

    # Removed explorer.finish_stage

    if exec_context:
        exec_context.finish_stage()

    return ApplicationRunSummary(
        total_candidates=total_candidates,
        applied=applied_count,
        already_applied=already_applied_count,
        skipped_local=skipped_local_count,
        native_applied=applied_count,
        ats_queue=ats_queue_count,
        generic_queue=generic_queue_count,
        manual_queue=manual_queue_count,
        unsupported=unsupported_count,
        policy_rejected=policy_rejected_count,
        dry_run_skipped=dry_run_skipped_count,
        run_limit_reached=run_limit_reached_count,
        failed=failed_count,
        manual_review=manual_review_count,
        applied_jobs=applied_jobs_list,
    )


def build_runtime_application_policy() -> ApplicationPolicy:
    """
    Build application policy from environment configuration.

    Runtime defaults are intentionally safe:
        - dry run enabled
        - maximum successful submissions per run
    """

    dry_run_value = (
        os.getenv(
            "APPLICATION_DRY_RUN",
            "true",
        )
        .strip()
        .lower()
    )

    dry_run = dry_run_value not in {
        "false",
        "0",
        "no",
    }

    max_applications_per_run = int(
        os.getenv(
            "MAX_APPLICATIONS_PER_RUN",
            "1",
        )
    )

    return ApplicationPolicy(
        dry_run=dry_run,
        max_applications_per_run=max_applications_per_run,
    )


def print_runtime_policy(
    policy: ApplicationPolicy,
) -> None:
    mode = "DRY RUN" if policy.dry_run else "LIVE"

    mode_color = Fore.YELLOW if policy.dry_run else Fore.RED

    print_section_title("application runtime policy")

    print(
        f"  {Fore.WHITE}"
        f"Mode                     : "
        f"{Style.RESET_ALL}"
        f"{mode_color}"
        f"{Style.BRIGHT}"
        f"{mode}"
        f"{Style.RESET_ALL}"
    )

    print(
        f"  {Fore.WHITE}"
        f"Max successful submissions per run : "
        f"{Style.RESET_ALL}"
        f"{Fore.CYAN}"
        f"{policy.max_applications_per_run if policy.max_applications_per_run is not None else 'UNLIMITED'}"
        f"{Style.RESET_ALL}"
    )


def classify_application_subtrack(result: dict) -> str:
    """
    Classify a scored job into one stable application subtrack.

    This metadata is used for:
        - application ledger analytics
        - application policy
        - portfolio balancing
        - conversion analysis

    Classification is deterministic and intentionally independent of
    acquisition query wording.
    """

    text = " ".join(
        [
            str(result.get("title") or ""),
            str(result.get("description") or ""),
        ]
    ).lower()

    if any(
        term in text
        for term in (
            "agentic ai",
            "ai agent",
            "multi-agent",
            "multi agent",
            "autogen",
            "langgraph",
            "semantic kernel",
        )
    ):
        return "AGENTIC_AI"

    if any(
        term in text
        for term in (
            "retrieval augmented generation",
            "retrieval-augmented generation",
            "rag ",
            "vector search",
            "vector database",
            "azure ai search",
            "semantic search",
            "embedding",
        )
    ):
        return "RAG_SEARCH"

    if any(
        term in text
        for term in (
            "llm",
            "large language model",
            "generative ai",
            "genai",
            "gen ai",
            "prompt engineering",
            "langchain",
            "azure openai",
            "openai",
        )
    ):
        return "GENAI_LLM"

    if any(
        term in text
        for term in (
            "full stack",
            "fullstack",
            "angular",
            "react",
            "node.js",
            "nodejs",
            "frontend",
            "backend",
        )
    ):
        return "FULLSTACK_AI"

    if any(
        term in text
        for term in (
            "mlops",
            "llmops",
            "ai platform",
            "machine learning platform",
            "model deployment",
            "model serving",
            "kubeflow",
            "mlflow",
        )
    ):
        return "AI_PLATFORM"

    if any(
        term in text
        for term in (
            "machine learning",
            "deep learning",
            "computer vision",
            "data scientist",
            "nlp",
            "pytorch",
            "tensorflow",
        )
    ):
        return "TRADITIONAL_ML"

    return "GENERAL_AI"


def classify_application_priority(
    result: dict,
    *,
    subtrack: str,
) -> str:
    """
    Convert job score and strategic role family into a stable priority tier.
    """

    score = int(
        result.get(
            "ai_score",
            result.get("score", 0),
        )
        or 0
    )

    strategic_subtracks = {
        "AGENTIC_AI",
        "RAG_SEARCH",
        "GENAI_LLM",
        "FULLSTACK_AI",
    }

    if score >= 85 and subtrack in strategic_subtracks:
        return "TIER_A"

    if score >= 75:
        return "TIER_B"

    return "TIER_C"


def enrich_application_metadata(
    results: list[dict],
) -> list[dict]:
    """
    Attach stable application metadata to scored pipeline results.
    """

    for result in results:
        subtrack = classify_application_subtrack(result)

        result["subtrack"] = subtrack

        result["priority"] = classify_application_priority(
            result,
            subtrack=subtrack,
        )

    return results


# ----------------------------------------------------------------------------------
# Main — orchestrates the full agent run
# ----------------------------------------------------------------------------------


def run_application_cycle(
    *,
    dry_run: bool | None = None,
    max_applications: int | None = None,
) -> dict[str, Any]:
    """
    Execute one complete acquisition, classification, selection,
    and application cycle.

    Returns structured run data for the orchestration layer.
    """

    # --------------------------------------------------------------------------
    # Step 2: Construct application dependencies
    # --------------------------------------------------------------------------

    omlx_client = OMLXClient(
        model="qwen3.5-4b",
    )

    llm_question_resolver = LLMQuestionResolver(
        client=omlx_client,
    )

    questionnaire_resolver = HybridQuestionResolver(
        llm_resolver=llm_question_resolver,
    )

    # --------------------------------------------------------------------------
    # Step 3: Cooldown-aware job acquisition with cache recovery
    # --------------------------------------------------------------------------

    job_cache = JobSearchCache(
        path=os.getenv(
            "JOB_SEARCH_CACHE_PATH",
            "data/job_search_cache.json",
        ),
        ttl_days=int(
            os.getenv(
                "JOB_SEARCH_CACHE_TTL_DAYS",
                "3",
            )
        ),
    )

    search_cooldown = SearchChallengeCooldown(
        path=os.getenv(
            "SEARCH_CHALLENGE_STATE_PATH",
            "data/search_challenge_state.json",
        ),
        cooldown_minutes=int(
            os.getenv(
                "SEARCH_CHALLENGE_COOLDOWN_MINUTES",
                "60",
            )
        ),
    )

    print("\n========== ACQUIRE_JOBS ==========")
    print("Entered acquire_jobs()")

    from src.orchestration.provider_factory import initialize_providers

    providers = initialize_providers()

    jobs, fetch_result = acquire_jobs(
        providers=providers,
        cache=job_cache,
        cooldown=search_cooldown,
    )

    # Note: Naukri client (jc) is accessed from providers if needed for enrichment
    jc = providers.get("naukri")

    print_acquisition_summary(
        jobs,
        fetch_result,
        suppressed=(jc is not None and search_cooldown.is_active()),
    )

    if not jobs:
        print(
            f"\n"
            f"{Fore.YELLOW}"
            f"  No fresh or cached jobs available."
            f"{Style.RESET_ALL}"
        )

        return {
            "acquired": 0,
            "classified": 0,
            "selected": 0,
            "summary": {
                "total_candidates": 0,
                "attempted": 0,
                "submitted": 0,
                "applied": 0,
                "already_applied": 0,
                "skipped_local": 0,
                "skipped_external": 0,
                "policy_rejected": 0,
                "dry_run_skipped": 0,
                "run_limit_reached": 0,
                "failed": 0,
                "manual_review": 0,
            },
        }

    # --------------------------------------------------------------------------
    # Step 4: Run AI filtering and ranking pipeline
    # --------------------------------------------------------------------------

    print_section_title("running AI filter pipeline")

    pipeline = JobFilterPipeline2()

    candidates = pipeline.pre_filter(jobs)

    detail_cache: dict[str, dict] = {}

    enriched_candidates = enrich_jobs_with_details(
        providers=providers,
        jobs=candidates,
        detail_cache=detail_cache,
    )

    final_jobs = pipeline.score_and_select(enriched_candidates)

    for result in final_jobs:

        result["score"] = result.get(
            "ai_score",
            result.get("score", 0),
        )

        result["ai_detail"] = result.get(
            "ai_reason",
            result.get("ai_detail", ""),
        )

    # --------------------------------------------------------------------------
    # Attach stable application metadata
    # --------------------------------------------------------------------------

    final_jobs = enrich_application_metadata(final_jobs)

    # Lookup containing score, AI detail, priority, subtrack, and other
    # classification metadata produced by the filtering pipeline.
    score_map = {result["job_id"]: result for result in final_jobs}

    allowed_job_ids = set(score_map.keys())

    print_pipeline_results(final_jobs)

    # --------------------------------------------------------------------------
    # Step 5: Load local application history
    # --------------------------------------------------------------------------

    ledger = ApplicationLedger(
        os.getenv(
            "APPLICATION_LEDGER_PATH",
            "data/application_ledger.db",
        )
    )

    # Backfill classification metadata for previously known jobs without
    # mutating their lifecycle status.
    for result in final_jobs:
        ledger.update_metadata(
            result["job_id"],
            score=result.get("score"),
            priority=str(result.get("priority") or ""),
            subtrack=str(result.get("subtrack") or ""),
        )

    applied_jobs_set = ledger.applied_job_ids()

    adaptive_strategy = build_adaptive_strategy(
        ledger.analytics_rows(),
        config=AdaptiveStrategyConfig(
            enabled=(
                os.getenv(
                    "ADAPTIVE_STRATEGY_ENABLED",
                    "true",
                )
                .strip()
                .lower()
                in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            ),
            minimum_applications=int(
                os.getenv(
                    "ADAPTIVE_MIN_APPLICATIONS",
                    "30",
                )
            ),
            minimum_responses=int(
                os.getenv(
                    "ADAPTIVE_MIN_RESPONSES",
                    "5",
                )
            ),
            base_minimum_score=int(
                os.getenv(
                    "AUTO_APPLY_MIN_SCORE",
                    "68",
                )
            ),
            base_max_applications_per_run=int(
                os.getenv(
                    "MAX_APPLICATIONS_PER_RUN",
                    "5",
                )
            ),
            minimum_group_samples=int(
                os.getenv(
                    "ADAPTIVE_MIN_GROUP_SAMPLES",
                    "5",
                )
            ),
            exploration_fraction=float(
                os.getenv(
                    "ADAPTIVE_EXPLORATION_FRACTION",
                    "0.20",
                )
            ),
            prior_strength=float(
                os.getenv(
                    "ADAPTIVE_PRIOR_STRENGTH",
                    "8.0",
                )
            ),
            decay_half_life_days=float(
                os.getenv(
                    "ADAPTIVE_DECAY_HALF_LIFE_DAYS",
                    "45.0",
                )
            ),
            response_weight=float(
                os.getenv(
                    "ADAPTIVE_RESPONSE_WEIGHT",
                    "1.0",
                )
            ),
            outcome_weight=float(
                os.getenv(
                    "ADAPTIVE_OUTCOME_WEIGHT",
                    "1.0",
                )
            ),
        ),
    )

    print_section_title("adaptive application strategy")

    print(f"  Active                  " f"{adaptive_strategy.active}")

    print(f"  Reason                  " f"{adaptive_strategy.reason}")

    print(f"  Historical applications " f"{adaptive_strategy.total_applications}")

    print(f"  Historical responses    " f"{adaptive_strategy.total_responses}")

    print(f"  Minimum score           " f"{adaptive_strategy.minimum_score}")

    print(f"  Suggested run limit     " f"{adaptive_strategy.max_applications_per_run}")

    print(
        f"  Preferred priorities    "
        f"{', '.join(adaptive_strategy.preferred_priorities) or 'NONE'}"
    )

    print(
        f"  Preferred subtracks     "
        f"{', '.join(adaptive_strategy.preferred_subtracks) or 'NONE'}"
    )

    # --------------------------------------------------------------------------
    # Step 6: Select and diversify filtered application candidates
    # --------------------------------------------------------------------------

    jobs_by_id = {job.job_id: job for job in jobs}

    ranked_allowed_jobs = [
        jobs_by_id[result["job_id"]]
        for result in final_jobs
        if result["job_id"] in jobs_by_id
    ]

    ranked_allowed_jobs = rank_candidates_adaptively(
        ranked_allowed_jobs,
        score_map=score_map,
        strategy=adaptive_strategy,
    )

    allowed_jobs = diversify_jobs(
        ranked_allowed_jobs,
        historical_company_counts=ledger.company_application_counts(),
        policy=DiversityPolicy(
            max_per_company_per_run=int(
                os.getenv("MAX_APPLICATIONS_PER_COMPANY_PER_RUN", "2")
            ),
            max_per_role_family_per_company=int(
                os.getenv("MAX_ROLE_FAMILY_PER_COMPANY", "1")
            ),
        ),
    )

    allowed_jobs = select_candidates_with_exploration(
        allowed_jobs,
        score_map=score_map,
        strategy=adaptive_strategy,
        limit=adaptive_strategy.max_applications_per_run,
    )

    print_section_title(f"applying to {len(allowed_jobs)} filtered jobs")

    # --------------------------------------------------------------------------
    # Step 7: Execute tested batch orchestration
    # --------------------------------------------------------------------------
    application_policy = build_runtime_application_policy()

    if dry_run is not None:
        application_policy = replace(
            application_policy,
            dry_run=dry_run,
        )

    if max_applications is not None:
        application_policy = replace(
            application_policy,
            max_applications_per_run=max_applications,
        )

    print_runtime_policy(application_policy)

    run_id = ledger.start_run(dry_run=application_policy.dry_run)

    ledger.record_strategy_decision(
        run_id=run_id,
        strategy=strategy_audit_payload(
            adaptive_strategy,
        ),
    )

    logger.info(
        "Application runtime policy: dry_run=%s max_applications_per_run=%s",
        application_policy.dry_run,
        application_policy.max_applications_per_run,
    )

    run_summary = run_application_batch(
        providers=providers,
        jobs=allowed_jobs,
        score_map=score_map,
        questionnaire_resolver=questionnaire_resolver,
        applied_jobs_set=applied_jobs_set,
        policy=application_policy,
        detail_cache=detail_cache,
        ledger=ledger,
        run_id=run_id,
    )

    ledger.finish_run(
        run_id,
        fetched=len(jobs),
        qualified=run_summary.total_candidates,
        applied=run_summary.applied,
        already_applied=run_summary.already_applied,
        failed=run_summary.failed,
    )

    # --------------------------------------------------------------------------
    # Step 8: Print final deterministic run summary
    # --------------------------------------------------------------------------

    print_summary(
        total_found=len(jobs),
        total_allowed=run_summary.total_candidates,
        applied=run_summary.applied,
        already_applied=run_summary.already_applied,
        skipped_local=run_summary.skipped_local,
        skipped_ext=run_summary.skipped_external,
        policy_rejected=run_summary.policy_rejected,
        dry_run_skipped=run_summary.dry_run_skipped,
        run_limit_reached=run_summary.run_limit_reached,
        failed=run_summary.failed,
    )

    return {
        "acquired": len(jobs),
        "classified": len(final_jobs),
        "selected": len(allowed_jobs),
        "summary": {
            "total_candidates": run_summary.total_candidates,
            "attempted": (
                run_summary.applied
                + run_summary.already_applied
                + run_summary.manual_review
                + run_summary.failed
            ),
            "submitted": run_summary.applied,
            "applied": run_summary.applied,
            "already_applied": run_summary.already_applied,
            "skipped_local": run_summary.skipped_local,
            "skipped_external": run_summary.skipped_external,
            "policy_rejected": run_summary.policy_rejected,
            "dry_run_skipped": run_summary.dry_run_skipped,
            "run_limit_reached": run_summary.run_limit_reached,
            "failed": run_summary.failed,
            "manual_review": run_summary.manual_review,
        },
    }


def main() -> None:
    run_application_cycle()


if __name__ == "__main__":
    main()
