import csv
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from src.client.job_client import NaukriJobClient
from src.client.naukri_client import NaukriLoginClient
from src.search.planner import SearchPlanner

load_dotenv(".env")


planner = SearchPlanner()
SEARCHES = planner.generate_queries()
if not SEARCHES:
    raise ValueError("SearchPlanner generated 0 queries.")

EXPERIENCE_LEVELS = [4, 5, 6, 7]

PAGES_PER_SEARCH = 2

JOB_AGE_DAYS = 7

RESULTS_PER_PAGE = 20

OUTPUT_FILE = Path("data/raw_jobs.csv")


def save_jobs(jobs):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "job_id",
        "title",
        "company",
        "location",
        "experience",
        "salary",
        "posted_date",
        "apply_link",
        "description",
        "tags",
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for job in jobs:
            writer.writerow(
                {
                    "job_id": job.job_id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "experience": job.experience,
                    "salary": job.salary,
                    "posted_date": job.posted_date,
                    "apply_link": job.apply_link,
                    "description": job.description,
                    "tags": " | ".join(job.tags),
                }
            )


def main():
    username = os.getenv("NAUKRI_USERNAME")
    password = os.getenv("NAUKRI_PASSWORD")

    if not username or not password:
        raise RuntimeError("USERNAME or PASSWORD missing from .env")

    print("[LOGIN] Authenticating")

    client = NaukriLoginClient(
        username,
        password,
    )

    client.login()

    print("[LOGIN] Success")

    job_client = NaukriJobClient(client)

    all_jobs = []

    seen_job_ids = set()

    total_requests = len(SEARCHES) * len(EXPERIENCE_LEVELS) * PAGES_PER_SEARCH

    request_number = 0

    for search in SEARCHES:

        keyword = search["keyword"]
        location = search["location"]

        for experience in EXPERIENCE_LEVELS:

            for page in range(
                1,
                PAGES_PER_SEARCH + 1,
            ):

                request_number += 1

                print(f"\n[SEARCH {request_number}/{total_requests}]")

                print(
                    f"keyword={keyword} | "
                    f"location={location} | "
                    f"experience={experience} | "
                    f"page={page}"
                )

                try:
                    jobs = job_client.search_jobs(
                        keyword=keyword,
                        location=location,
                        experience=experience,
                        job_age=JOB_AGE_DAYS,
                        page=page,
                        results_per_page=RESULTS_PER_PAGE,
                    )

                except Exception as exc:
                    print(f"[ERROR] Search failed: {exc}")

                    time.sleep(3)

                    continue

                new_count = 0

                for job in jobs:

                    if not job.job_id:
                        continue

                    if job.job_id in seen_job_ids:
                        continue

                    seen_job_ids.add(job.job_id)

                    all_jobs.append(job)

                    new_count += 1

                print(
                    f"[RESULT] fetched={len(jobs)} "
                    f"new={new_count} "
                    f"unique_total={len(all_jobs)}"
                )

                if not jobs:
                    break

                time.sleep(1.5)

    save_jobs(all_jobs)

    print("\n" + "=" * 70)

    print(f"Unique jobs: {len(all_jobs)}")

    print(f"Saved to: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
