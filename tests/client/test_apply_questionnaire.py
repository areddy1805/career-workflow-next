import csv
import json
import os
from datetime import UTC, datetime

from dotenv import load_dotenv

from config.candidate_profile import CANDIDATE_PROFILE
from src.client.job_client import NaukriJobClient
from src.client.naukri_client import NaukriLoginClient
from src.models.models import Job
from src.utils.questionnaire_resolver import resolve_answer

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
        raise RuntimeError(f"Job ID {job_id} not found in data/scored_jobs.csv")

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

    if not username or not password:
        raise RuntimeError("USERNAME or PASSWORD missing from .env")

    job = load_job(TEST_JOB_ID)

    print("=" * 100)
    print("QUESTIONNAIRE APPLY TEST")
    print("=" * 100)

    print(f"Job:      {job.title}")
    print(f"Company:  {job.company}")
    print(f"Job ID:   {job.job_id}")
    print(f"Location: {job.location}")

    print("\n[1] Logging in...")

    client = NaukriLoginClient(
        username,
        password,
    )

    client.login()

    print("[OK] Login successful")

    jc = NaukriJobClient(client)

    sid = datetime.now(UTC).strftime("%Y%m%d%H%M%S") + "0000000"

    print("\n[2] Starting apply workflow...")

    initial = jc.apply_job(
        job,
        mandatory_skills=[],
        optional_skills=[],
        sid=sid,
        source="search",
    )

    print("[OK] Initial apply response received")

    jobs = initial.get("jobs") or []

    if not jobs:
        print("\n[STOP] No jobs object in response")

        print(
            json.dumps(
                initial,
                indent=2,
                ensure_ascii=False,
            )
        )

        return

    job_result = jobs[0]

    questionnaire = job_result.get("questionnaire") or []

    if not questionnaire:
        print("\n[RESULT] No questionnaire returned.")
        print("The initial apply request may have completed the application.")

        print("\n[RAW RESPONSE]")

        print(
            json.dumps(
                initial,
                indent=2,
                ensure_ascii=False,
            )
        )

        return

    print(f"[OK] Questionnaire count: " f"{len(questionnaire)}")

    print("\n[3] Resolving questionnaire answers...")

    answers = {}
    unresolved = []

    for question_data in questionnaire:
        question_id = question_data["questionId"]

        question_text = question_data.get("questionName") or ""

        question_type = question_data.get("questionType") or ""

        mandatory = question_data.get(
            "isMandatory",
            False,
        )

        category = question_data.get("category") or ""

        answer = resolve_answer(
            question_data,
            CANDIDATE_PROFILE,
        )

        print("\n" + "-" * 100)

        print(f"Question ID:   {question_id}")
        print(f"Question:      {question_text}")
        print(f"Type:          {question_type}")
        print(f"Category:      {category}")
        print(f"Mandatory:     {mandatory}")
        print(f"Resolved:      {answer}")

        if answer is None:
            unresolved.append(question_data)

            continue

        answers[question_id] = answer

    if unresolved:
        print("\n" + "=" * 100)
        print("[STOP] UNRESOLVED QUESTIONS")
        print("=" * 100)

        for question_data in unresolved:
            print(
                f'- {question_data.get("questionName")} '
                f'[{question_data.get("questionType")}]'
            )

        print("\nApplication state: MANUAL_REVIEW")

        print("No questionnaire answers were submitted.")

        return

    print("\n" + "=" * 100)
    print("RESOLVED ANSWERS")
    print("=" * 100)

    print(
        json.dumps(
            answers,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nWARNING: THE NEXT ACTION SUBMITS " "THE QUESTIONNAIRE ANSWERS")

    confirmation = input(f"Type SUBMIT {job.job_id} to continue: ").strip()

    if confirmation != f"SUBMIT {job.job_id}":
        print("[STOP] Confirmation did not match")

        return

    print("\n[4] Submitting questionnaire answers...")

    result = jc.submit_questionnaire_answers(
        job=job,
        answers=answers,
        sid=sid,
        source="search",
    )

    print("\n[RAW FINAL RESPONSE]")

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
