from __future__ import annotations

import argparse
import json
import os

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

    pipeline = CareerWorkflowPipeline(
        dry_run=not args.live,
        max_applications=max_applications,
        acquisition_mode=args.acquisition_mode,
        force_live=args.force_live,
        acquisition_provider=args.provider,
    )
    result = pipeline.run()
    print()
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
