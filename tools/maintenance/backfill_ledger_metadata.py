from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from apply_agent import (
    classify_application_priority,
    classify_application_subtrack,
)
from src.application.ledger import ApplicationLedger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backfill deterministic priority/subtrack metadata for historical ledger rows."
    )
    parser.add_argument(
        "--ledger",
        default=os.getenv("APPLICATION_LEDGER_PATH", "data/application_ledger.db"),
    )
    parser.add_argument(
        "--default-score",
        type=int,
        default=None,
        help="Optional score for rows that have no score. Omit to preserve UNSCORED rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ledger = ApplicationLedger(args.ledger)
    rows = ledger.analytics_rows()
    updated = 0

    for row in rows:
        score = row.get("score")
        if score is None:
            score = args.default_score

        payload = {
            "title": row.get("title") or "",
            "description": "",
            "score": score or 0,
        }
        subtrack = row.get("subtrack") or classify_application_subtrack(payload)
        priority = row.get("priority")
        if not priority and score is not None:
            priority = classify_application_priority(payload, subtrack=subtrack)

        ledger.update_metadata(
            str(row["job_id"]),
            score=score,
            priority=str(priority or ""),
            subtrack=str(subtrack or ""),
        )
        updated += 1

    print(
        {
            "rows_scanned": len(rows),
            "rows_updated": updated,
            "quality": ledger.metadata_completeness(),
        }
    )


if __name__ == "__main__":
    main()
