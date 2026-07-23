from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

from src.application.ledger import ApplicationLedger
from src.client.naukri_client import NaukriLoginClient

load_dotenv()


LEDGER_PATH = os.getenv(
    "APPLICATION_LEDGER_PATH",
    "data/application_ledger.db",
)

STALE_APPLICATION_DAYS = int(
    os.getenv(
        "STALE_APPLICATION_DAYS",
        "14",
    )
)


def build_client() -> NaukriLoginClient:
    username = os.getenv("NAUKRI_USERNAME")
    password = os.getenv("NAUKRI_PASSWORD")

    if not username:
        raise RuntimeError("NAUKRI_USERNAME environment variable is not set")

    if not password:
        raise RuntimeError("NAUKRI_PASSWORD environment variable is not set")

    client = NaukriLoginClient(
        username,
        password,
    )

    client.login()

    return client


def fetch_all_application_history(
    client: NaukriLoginClient,
) -> list[dict[str, Any]]:
    """
    Fetch and normalize server-side application history.
    """

    raw_history = client.get_application_history()

    history = client.parse_history(
        raw_history,
    )

    return history


def reconcile_application_history(
    *,
    client: NaukriLoginClient,
    ledger: ApplicationLedger,
) -> dict[str, Any]:
    """
    Fetch server-side application history and reconcile it into the ledger.
    """

    history = fetch_all_application_history(
        client,
    )

    changed = ledger.reconcile_server_history(
        history,
    )

    return {
        "history": history,
        "fetched": len(history),
        "changed": changed,
    }


def print_local_summary(
    ledger: ApplicationLedger,
) -> None:
    print("\nLOCAL APPLICATION SUMMARY")

    summary = ledger.summary()

    if not summary:
        print("  No local applications.")
        return

    for status, count in sorted(
        summary.items(),
    ):
        print(f"  {status:<28} {count:>6}")


def print_lifecycle_summary(
    ledger: ApplicationLedger,
) -> None:
    print("\nAPPLICATION LIFECYCLE")

    summary = ledger.lifecycle_summary()

    if not summary:
        print("  No lifecycle data.")
        return

    for stage, count in sorted(
        summary.items(),
    ):
        print(f"  {stage:<28} {count:>6}")


def print_stale_applications(
    ledger: ApplicationLedger,
) -> None:
    print(f"\nSTALE APPLICATIONS " f"(>{STALE_APPLICATION_DAYS} days)")

    applications = ledger.stale_applications(
        older_than_days=STALE_APPLICATION_DAYS,
    )

    if not applications:
        print("  None")
        return

    for application in applications:
        print(
            f"  {application.get('job_id', '')} | "
            f"{application.get('title', '')} | "
            f"{application.get('company', '')} | "
            f"{application.get('lifecycle_stage', '')} | "
            f"{application.get('server_status') or 'NO_STATUS'}"
        )


def print_funnel_breakdown(
    ledger: ApplicationLedger,
    *,
    dimension: str,
) -> None:
    from src.application.analytics import breakdown

    print(f"\nFUNNEL BREAKDOWN BY {dimension.upper()}")

    rows = breakdown(
        ledger.analytics_rows(),
        dimension=dimension,
    )

    if not rows:
        print("  No data.")
        return

    for row in rows:
        print(
            f"  {str(row['dimension_value']):<24} "
            f"total={int(row['total']):>4} "
            f"response={float(row['response_rate']):>5.1f}% "
            f"interview={int(row['interview']):>3} "
            f"offer={int(row['offer']):>3}"
        )


def main() -> None:
    client = build_client()

    ledger = ApplicationLedger(
        LEDGER_PATH,
    )

    result = reconcile_application_history(
        client=client,
        ledger=ledger,
    )

    print(f"Server applications fetched : " f"{result['fetched']}")

    print(f"New/changed records         : " f"{result['changed']}")

    print_local_summary(
        ledger,
    )

    print_lifecycle_summary(
        ledger,
    )

    print_stale_applications(
        ledger,
    )

    print_funnel_breakdown(
        ledger,
        dimension="priority",
    )

    print_funnel_breakdown(
        ledger,
        dimension="subtrack",
    )


if __name__ == "__main__":
    main()
