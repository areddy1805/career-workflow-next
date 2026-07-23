import os

from dotenv import load_dotenv

from src.client.naukri_client import NaukriLoginClient


def main():
    load_dotenv(".env")

    username = os.getenv("NAUKRI_USERNAME")
    password = os.getenv("NAUKRI_PASSWORD")

    print("[1] Logging in...")

    client = NaukriLoginClient(
        username,
        password,
    )

    client.login()

    print("[OK] Login successful")

    print("[2] Fetching application history...")

    print("\n[DESKTOP MODE]")

    desktop_raw = client.get_application_history(
        page_size=20,
        days=90,
        page_number=1,
        mobile=False,
    )

    print("matchingRowsCount:", desktop_raw.get("matchingRowsCount"))
    print("applyDetails type:", type(desktop_raw.get("applyDetails")))
    print("applyDetails:", desktop_raw.get("applyDetails"))

    print("\n[MOBILE MODE]")

    mobile_raw = client.get_application_history(
        page_size=20,
        days=90,
        page_number=1,
        mobile=True,
    )

    print("matchingRowsCount:", mobile_raw.get("matchingRowsCount"))
    print("applyDetails type:", type(mobile_raw.get("applyDetails")))

    details = mobile_raw.get("applyDetails")

    if isinstance(details, list):
        print("applyDetails count:", len(details))

        for item in details[:5]:
            print(
                item.get("jobId"),
                "|",
                item.get("jobTitle"),
                "|",
                item.get("company"),
            )
    else:
        print("applyDetails:", details)

    print("[OK] Raw history fetched")
    # print("\nHistory metadata:")
    # print("days:", raw.get("days"))
    # print("pageSize:", raw.get("pageSize"))
    # print("pageNumber:", raw.get("pageNumber"))
    # print("matchingRowsCount:", raw.get("matchingRowsCount"))
    # print("applyDetails type:", type(raw.get("applyDetails")))
    # print("applyDetails value:", raw.get("applyDetails"))

    # print("\nTop-level keys:")
    # print(raw.keys())

    # # history = client.parse_history(raw)

    # print(f"\nParsed applications: {len(history)}")

    # for i, item in enumerate(history[:20], 1):
    #     print("=" * 100)
    #     print(f"{i}. {item.job_title}")
    #     print(f"Company: {item.company}")
    #     print(f"Job ID:  {item.job_id}")
    #     print(f"Location: {item.location}")
    #     print(f"Open:     {item.is_open}")

    #     print("Statuses:")

    #     for status in item.statuses:
    #         print(f"  {status.status_value} | " f"{status.date_time}")


if __name__ == "__main__":
    main()
