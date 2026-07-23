import os

from dotenv import load_dotenv

from src.client.naukri_client import NaukriLoginClient

load_dotenv(".env")


def main():
    username = os.getenv("NAUKRI_USERNAME")
    password = os.getenv("NAUKRI_PASSWORD")

    if not username or not password:
        raise RuntimeError("USERNAME or PASSWORD missing")

    print("[1] Creating client")
    client = NaukriLoginClient(username, password)

    print("[2] Attempting login")
    session = client.login()

    print("[OK] Login successful")
    print("[OK] Session created:", session is not None)
    print("[OK] Auth token present:", bool(session.bearer_token))


if __name__ == "__main__":
    main()
