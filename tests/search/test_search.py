import os

from dotenv import load_dotenv

from src.client.job_client import NaukriJobClient
from src.client.naukri_client import NaukriLoginClient

load_dotenv(".env")


def main():
    username = os.getenv("NAUKRI_USERNAME")
    password = os.getenv("NAUKRI_PASSWORD")

    if not username or not password:
        raise RuntimeError("USERNAME or PASSWORD missing")

    print("[1] Logging in...")

    client = NaukriLoginClient(username, password)
    client.login()

    print("[OK] Login successful")

    print("[2] Creating job client...")

    job_client = NaukriJobClient(client)

    print("[3] Running one search request...")

    jobs = job_client.search_jobs(
        keyword="AI Engineer",
        location="Pune",
        experience=5,
        job_age=3,
        page=1,
        results_per_page=20,
    )

    print(f"[OK] Jobs returned: {len(jobs)}")

    for index, job in enumerate(jobs[:10], start=1):
        print("\n" + "=" * 80)
        print(f"{index}. {job.title}")
        print(f"Company:    {job.company}")
        print(f"Location:   {job.location}")
        print(f"Experience: {job.experience}")
        print(f"Posted:     {job.posted_date}")
        print(f"Job ID:     {job.job_id}")
        print(f"Skills:     {', '.join(job.tags[:10])}")


if __name__ == "__main__":
    main()
