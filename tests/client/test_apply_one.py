import csv
import json
import os
import sys

from dotenv import load_dotenv

from src.client.job_client import NaukriJobClient
from src.client.naukri_client import NaukriLoginClient
from src.models.models import Job

TEST_JOB_ID = "030726014753"


def load_job(job_id: str) -> Job:
    with open(
        "data/scored_jobs.csv",
        encoding="utf-8",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    row = next(
        (r for r in rows if r["job_id"] == job_id),
        None,
    )

    if row is None:
        raise RuntimeError(f"Job ID {job_id} not found in scored_jobs.csv")

    tags = [tag.strip() for tag in (row.get("tags") or "").split(",") if tag.strip()]

    return Job(
        job_id=row["job_id"],
        title=row["title"],
        company=row["company"],
        location=row["location"],
        experience=row.get("experience", ""),
        salary=row.get("salary", ""),
        posted_date=row.get("posted_date", ""),
        apply_url=row.get("apply_url", ""),
        description=row.get("description", ""),
        tags=tags,
    )


def main():
    load_dotenv(".env")

    username = os.getenv("NAUKRI_USERNAME")
    password = os.getenv("NAUKRI_PASSWORD")

    job = load_job(TEST_JOB_ID)

    print("=" * 100)
    print("CONTROLLED APPLY TEST")
    print("=" * 100)

    print(f"Job ID:   {job.job_id}")
    print(f"Title:    {job.title}")
    print(f"Company:  {job.company}")
    print(f"Location: {job.location}")

    print("\n[1] Logging in...")

    client = NaukriLoginClient(
        username,
        password,
    )

    client.login()

    print("[OK] Login successful")

    jc = NaukriJobClient(client)

    print("\n[2] Fetching job details...")

    details = jc.get_job_details(job.job_id)

    job_data = details.get("job", {})

    print("[OK] Job details fetched")
    print(
        "responseManager:",
        job_data.get("responseManager"),
    )

    print("\n[3] Checking external apply status...")

    response_manager = job_data.get("responseManager")

    if response_manager == "companyUrl":
        print("[STOP] External application job")
        sys.exit(0)

    print("[OK] Internal Naukri apply workflow")

    print("\n" + "=" * 100)
    print("WARNING: THE NEXT ACTION SUBMITS A REAL APPLICATION")
    print("=" * 100)

    confirmation = input(f"Type APPLY {job.job_id} to submit: ").strip()

    if confirmation != f"APPLY {job.job_id}":
        print("[STOP] Confirmation did not match")
        sys.exit(0)

    print("\n[4] Submitting one application...")

    try:
        result = jc.apply_job(
            job,
            mandatory_skills=[],
            optional_skills=[],
            source="search",
        )

        print("\n[RAW APPLY RESPONSE]")
        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

    except Exception as exc:
        print("\n[APPLY EXCEPTION]")
        print("Type:", type(exc).__name__)
        print("Message:", str(exc))
        raise


if __name__ == "__main__":
    main()
