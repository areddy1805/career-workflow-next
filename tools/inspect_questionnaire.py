import json
import os

from dotenv import load_dotenv

from src.client.job_client import NaukriJobClient
from src.client.naukri_client import NaukriLoginClient
from src.models.models import Job

JOB_ID = "290626015208"


def main():
    load_dotenv(".env")

    username = os.getenv("NAUKRI_USERNAME")
    password = os.getenv("NAUKRI_PASSWORD")

    client = NaukriLoginClient(username, password)
    client.login()

    job_client = NaukriJobClient(client)

    job = Job(
        job_id=JOB_ID,
        title="Generative AI Engineer",
        company="Yash Technologies",
        location="Pune",
        experience="",
        salary="",
        posted_date="",
        apply_link="",
        description="",
        tags=[],
    )

    response = job_client.apply_job(
        job,
        source="search",
    )

    questionnaire = response.get("jobs", [{}])[0].get("questionnaire", [])

    for q in questionnaire:
        print("=" * 120)
        print(json.dumps(q, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
