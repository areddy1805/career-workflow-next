from __future__ import annotations

import argparse
import json
import os
import sys

from src.orchestration import CareerWorkflowPipeline

LIVE_CONFIRMATION = "APPLY_LIVE"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the Career Workflow orchestration pipeline"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live application submission. Default is dry-run.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (fast, deterministic, minimal acquisition).",
    )
    parser.add_argument(
        "--debug-llm",
        action="store_true",
        help="Run in debug mode to isolate LLM hangs.",
    )
    parser.add_argument(
        "--debug-limit",
        type=int,
        default=20,
        help="Number of jobs to evaluate in debug mode. Default is 20.",
    )
    parser.add_argument(
        "--debug-offset",
        type=int,
        default=0,
        help="Start offset of jobs in debug mode. Default is 0.",
    )
    parser.add_argument(
        "--debug-timeout",
        type=float,
        default=60.0,
        help="Per-job timeout in seconds for debug mode. Default is 60.0.",
    )
    parser.add_argument(
        "--max-applications",
        type=int,
        default=None,
        help="Optional attempt cap. Omit for uncapped execution.",
    )
    parser.add_argument(
        "--acquisition-mode", choices=("full", "incremental"), default="full"
    )
    parser.add_argument(
        "--confirm-live",
        default="",
        help=f"Required with --live. Must equal {LIVE_CONFIRMATION!r}.",
    )
    parser.add_argument(
        "--canary",
        action="store_true",
        help="Force a live run to at most one application.",
    )
    parser.add_argument(
        "--force-live",
        action="store_true",
        help="Bypass search challenge cooldowns and force a live acquisition.",
    )
    parser.add_argument(
        "--provider",
        choices=("all", "naukri", "jobspy"),
        default="all",
        help="Specify which acquisition providers to run. Default is all.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.debug_llm:
        print(f"[DEBUG-LLM] Entering debug mode (Limit={args.debug_limit}, Offset={args.debug_offset}, Timeout={args.debug_timeout}s)")
        from src.search.job_search_cache import JobSearchCache
        from src.client.job_classifier import JobFilterPipeline2
        
        print("[DEBUG-LLM] Loaded cache")
        cache = JobSearchCache()
        all_jobs = cache.load()
        print(f"[DEBUG-LLM] Total cached jobs available: {len(all_jobs)}")
        
        start_idx = args.debug_offset
        end_idx = args.debug_offset + args.debug_limit
        selected_jobs = all_jobs[start_idx:end_idx]
        print(f"[DEBUG-LLM] Selected {len(selected_jobs)} jobs (Jobs {start_idx + 1} to {start_idx + len(selected_jobs)} of {len(all_jobs)})")
        
        # Classifier expects dictionaries
        job_dicts = []
        for j in selected_jobs:
            jd = j if isinstance(j, dict) else j.__dict__
            job_dicts.append(jd)
            
        from src.client.inference_service import InferenceService
        inference_service = InferenceService(cache_manager=None)
        classifier = JobFilterPipeline2(test_mode=False, inference_service=inference_service)
        job_dicts = classifier.normalize_jobs(job_dicts)
        
        print("[DEBUG-LLM] Entering ai_score_batch")
        classifier.ai_score_batch(job_dicts, timeout=args.debug_timeout, global_offset=args.debug_offset)
        print("[DEBUG-LLM] Classification complete")
        sys.exit(0)

    if args.live:
        env_confirmation = os.getenv("LIVE_APPLICATION_CONFIRMATION", "")
        confirmation = args.confirm_live or env_confirmation
        if confirmation != LIVE_CONFIRMATION:
            raise SystemExit(
                "Live mode blocked. Pass --confirm-live APPLY_LIVE or set "
                "LIVE_APPLICATION_CONFIRMATION=APPLY_LIVE."
            )

    max_applications = args.max_applications
    if args.live and args.canary:
        max_applications = 1

    if args.test:
        os.environ["MAX_KEYWORDS"] = "3"
        os.environ["MAX_PAGES"] = "1"
        os.environ["MAX_EXPERIENCE_COMBINATIONS"] = "1"
        os.environ["BROWSER_DISABLED"] = "1"
        os.environ["RECONCILIATION_DISABLED"] = "1"
        os.environ["SCHEDULER_DISABLED"] = "1"
        os.environ["TELEMETRY_OPTIONAL"] = "1"
        os.environ["DETERMINISTIC_SEED"] = "42"
        max_applications = 0
        args.acquisition_mode = "incremental"
        args.live = False

    pipeline = CareerWorkflowPipeline(
        dry_run=not args.live,
        max_applications=max_applications,
        acquisition_mode=args.acquisition_mode,
        force_live=args.force_live,
        acquisition_provider=args.provider,
        test_mode=args.test,
    )

    import time

    start_time = time.time()

    result = pipeline.run()

    end_time = time.time()
    if args.test and (end_time - start_time) > 60:
        print(
            f"\nWARNING: Test mode exceeded 60 seconds (took {end_time - start_time:.1f}s)"
        )

    print()
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
