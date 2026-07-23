import argparse
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.acquisition.providers.jobspy_provider import JobSpyProvider, JobSpyConfig
from src.models.models import Job

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("validate_jobspy")


def main():
    parser = argparse.ArgumentParser(description="Standalone JobSpy validation script.")
    parser.add_argument(
        "--keyword", type=str, default="AI Engineer", help="Keyword to search."
    )
    parser.add_argument(
        "--location", type=str, default="Pune", help="Location to search."
    )
    parser.add_argument(
        "--site",
        type=str,
        default="google",
        choices=["google", "indeed", "linkedin"],
        help="JobSpy site to search.",
    )
    parser.add_argument(
        "--results", type=int, default=3, help="Number of results wanted."
    )
    parser.add_argument(
        "--country", type=str, default="india", help="Indeed country parameter."
    )
    args = parser.parse_args()

    print("=" * 60)
    print("STANDALONE JOBSPY VALIDATION")
    print("=" * 60)
    print(f"Keyword : {args.keyword}")
    print(f"Location: {args.location}")
    print(f"Site    : {args.site}")
    print(f"Results : {args.results}")
    print(f"Country : {args.country}")
    print("-" * 60)

    # 1. Direct JobSpy Scraper Test
    print("\n--- Phase 1: Direct JobSpy scraping ---")
    try:
        import jobspy

        print("Importing python-jobspy: SUCCESS")
    except ImportError as e:
        print(f"Importing python-jobspy: FAILED ({e})")
        sys.exit(1)

    try:
        df = jobspy.scrape_jobs(
            site_name=[args.site],
            search_term=args.keyword,
            location=args.location,
            results_wanted=args.results,
            country_indeed=args.country,
            verbose=1,
        )
        if df is None or df.empty:
            print("Direct JobSpy scrape succeeded but returned 0 jobs.")
            raw_jobs_count = 0
        else:
            raw_jobs_count = len(df)
            print(f"Direct JobSpy scrape succeeded! Found {raw_jobs_count} raw jobs.")
            print("\nFirst row sample:")
            first_row = df.iloc[0].to_dict()
            for k, v in list(first_row.items())[:10]:
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"Direct JobSpy scrape FAILED: {e}")
        df = None
        raw_jobs_count = 0

    # 2. Pipeline Adapter Test
    print("\n--- Phase 2: Pipeline JobSpyProvider adapter ---")
    cfg = JobSpyConfig(
        enabled=True,
        sites=[args.site],
        results_wanted=args.results,
        country_indeed=args.country,
    )
    provider = JobSpyProvider(cfg)

    try:
        jobs = provider.search(
            keyword=args.keyword, location=args.location, site=args.site
        )
        print(f"Provider search succeeded! Returned {len(jobs)} normalized jobs.")
        if jobs:
            print("\nFirst normalized Job details:")
            job = jobs[0]
            print(f"  job_id          : {job.job_id}")
            print(f"  title           : {job.title}")
            print(f"  company         : {job.company}")
            print(f"  location        : {job.location}")
            print(f"  experience      : {job.experience}")
            print(f"  salary          : {job.salary}")
            print(f"  posted_date     : {job.posted_date}")
            print(f"  apply_link      : {job.apply_link}")
            print(f"  provider_id     : {job.provider_id}")
            print(f"  provider_name   : {job.provider_name}")
            print(f"  provider_source : {job.provider_source}")
            print(f"  provider_url    : {job.provider_url}")
            print(f"  provider_job_id : {job.provider_job_id}")

            # Check validation criteria
            assert job.provider_id == "jobspy", "provider_id mismatch"
            assert job.provider_source == args.site, "provider_source mismatch"
            assert job.provider_job_id, "provider_job_id missing"
            print("\nMetadata Verification: PASSED")
        else:
            print("\nNo jobs normalized.")
    except Exception as e:
        print(f"Provider search FAILED: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
