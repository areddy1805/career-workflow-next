import argparse
import dataclasses
from src.orchestration.scheduler import run_scheduler, SchedulerConfig

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the scheduler daemon.")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run the pipeline immediately upon startup",
    )
    parser.add_argument(
        "--interactive", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument(
        "--session-hours",
        type=float,
        help="Automatically exit after this many hours (interactive mode)",
    )
    parser.add_argument(
        "--incremental",
        type=int,
        help="Custom incremental interval in minutes (interactive mode)",
    )
    parser.add_argument(
        "--force-live",
        action="store_true",
        help="Bypass challenge cooldown and force live search.",
    )
    args = parser.parse_args()

    config = SchedulerConfig.from_env()
    run_immediately = args.run_now
    session_hours = None

    if args.interactive:
        run_immediately = True
        interval = args.incremental if args.incremental is not None else 30
        config = dataclasses.replace(config, incremental_interval_minutes=interval)
        if args.session_hours:
            session_hours = args.session_hours

    run_scheduler(
        config=config,
        run_immediately=run_immediately,
        session_hours=session_hours,
        force_live=args.force_live,
    )
