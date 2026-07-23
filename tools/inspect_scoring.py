import csv
import random
from collections import defaultdict

INPUT_FILE = "data/scored_jobs.csv"

random.seed(42)


def print_job(row):
    print("-" * 120)

    print(
        f'SCORE={row["score"]} | '
        f'DECISION={row["decision"]} | '
        f'TRACK={row["track"]} | '
        f'LOCATION={row["location_status"]}'
    )

    print(f'TITLE:    {row["title"]}')
    print(f'COMPANY:  {row["company"]}')
    print(f'LOCATION: {row["location"]}')
    print(f'EXP:      {row["experience"]}')

    print(f'MATCHES:  {row["matches"]}')

    if row["reason"]:
        print(f'REASON:   {row["reason"]}')

    description = row["description"].replace("\n", " ").strip()

    print(f"DESC:     {description[:700]}")


def section(title, rows):
    print("\n")
    print("=" * 120)
    print(title)
    print("=" * 120)

    for row in rows:
        print_job(row)


def main():
    with open(
        INPUT_FILE,
        encoding="utf-8",
        newline="",
    ) as file:
        jobs = list(csv.DictReader(file))

    groups = defaultdict(list)

    for job in jobs:
        groups[
            (
                job["decision"],
                job["track"],
                job["location_status"],
            )
        ].append(job)

    # Highest-scoring AI jobs
    ai_shortlist = [
        j for j in jobs if j["decision"] == "SHORTLIST" and j["track"] == "AI"
    ]

    ai_shortlist.sort(
        key=lambda x: int(x["score"]),
        reverse=True,
    )

    section(
        "TOP 25 AI SHORTLIST",
        ai_shortlist[:25],
    )

    # Lowest-scoring jobs that barely entered shortlist
    shortlist_boundary = [j for j in jobs if j["decision"] == "SHORTLIST"]

    shortlist_boundary.sort(
        key=lambda x: int(x["score"]),
    )

    section(
        "25 JOBS JUST ABOVE SHORTLIST THRESHOLD",
        shortlist_boundary[:25],
    )

    # Random borderline jobs
    borderline = [j for j in jobs if j["decision"] == "BORDERLINE"]

    section(
        "30 RANDOM BORDERLINE JOBS",
        random.sample(
            borderline,
            min(30, len(borderline)),
        ),
    )

    # Highest rejected jobs
    rejected = [j for j in jobs if j["decision"] == "REJECT"]

    rejected.sort(
        key=lambda x: int(x["score"]),
        reverse=True,
    )

    section(
        "TOP 30 REJECTED JOBS",
        rejected[:30],
    )

    # Pune/Remote rejected jobs
    rejected_local = [
        j
        for j in jobs
        if j["decision"] == "REJECT" and j["location_status"] == "ACCEPT"
    ]

    rejected_local.sort(
        key=lambda x: int(x["score"]),
        reverse=True,
    )

    section(
        "ALL REJECTED PUNE / REMOTE / INDIA JOBS",
        rejected_local,
    )

    # Non-local highly scored jobs
    nonlocal_high = [
        j
        for j in jobs
        if j["decision"] == "SHORTLIST" and j["location_status"] == "REVIEW"
    ]

    nonlocal_high.sort(
        key=lambda x: int(x["score"]),
        reverse=True,
    )

    section(
        "TOP 30 HIGH-SCORE NON-LOCAL JOBS",
        nonlocal_high[:30],
    )


if __name__ == "__main__":
    main()
