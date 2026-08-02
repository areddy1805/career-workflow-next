from unittest.mock import Mock

import pytest

from src.client.job_client import NaukriJobClient
from src.exceptions.exceptions import NaukriParseError, NaukriSearchChallengeError


def make_client_with_session(session: Mock) -> NaukriJobClient:
    login_client = Mock()
    login_client.session = session
    login_client._build_headers.return_value = {
        "accept": "application/json",
        "appid": "105",
        "clientid": "d3skt0p",
        "content-type": "application/json",
        "referer": "https://www.naukri.com/nlogin/login",
        "systemid": "jobseeker",
        "x-requested-with": "XMLHttpRequest",
    }
    return NaukriJobClient(login_client)


def make_response(status_code: int, body: dict) -> Mock:
    import json

    resp = Mock()
    resp.status_code = status_code
    resp.text = json.dumps(body)
    resp.ok = status_code < 400
    resp.json.return_value = body
    return resp


def make_jobs_response() -> Mock:
    return make_response(
        200,
        {
            "jobDetails": [
                {
                    "jobId": "JOB-1",
                    "title": "AI Engineer",
                    "companyName": "Acme",
                    "placeholders": [],
                }
            ]
        },
    )


def test_single_challenge_retries_and_succeeds(monkeypatch):
    session = Mock()
    session.get.side_effect = [
        make_response(406, {"message": "recaptcha required", "statusCode": 406}),
        make_jobs_response(),
    ]
    client = make_client_with_session(session)

    monkeypatch.setattr(client, "_build_seo_key", lambda *a, **k: "seo-key")
    monkeypatch.setattr(client, "format_jobs", lambda jobs: jobs)
    monkeypatch.setattr("src.client.job_client.time.sleep", lambda _s: None)

    jobs = client.search_jobs(keyword="AI Engineer", location="Pune", page=1)

    assert len(jobs) == 1
    assert jobs[0].job_id == "JOB-1"
    assert session.get.call_count == 2


def test_two_challenges_then_success(monkeypatch):
    session = Mock()
    session.get.side_effect = [
        make_response(406, {"message": "recaptcha required", "statusCode": 406}),
        make_response(406, {"message": "recaptcha required", "statusCode": 406}),
        make_jobs_response(),
    ]
    client = make_client_with_session(session)

    monkeypatch.setattr(client, "_build_seo_key", lambda *a, **k: "seo-key")
    monkeypatch.setattr(client, "format_jobs", lambda jobs: jobs)
    monkeypatch.setattr("src.client.job_client.time.sleep", lambda _s: None)

    jobs = client.search_jobs(keyword="AI Engineer", location="Pune", page=1)

    assert len(jobs) == 1
    assert session.get.call_count == 3


def test_consecutive_challenges_raise_challenge_error(monkeypatch):
    session = Mock()
    session.get.return_value = make_response(
        406, {"message": "recaptcha required", "statusCode": 406}
    )
    client = make_client_with_session(session)

    monkeypatch.setattr(client, "_build_seo_key", lambda *a, **k: "seo-key")
    monkeypatch.setattr("src.client.job_client.time.sleep", lambda _s: None)

    with pytest.raises(NaukriSearchChallengeError):
        client.search_jobs(keyword="AI Engineer", location="Pune", page=1)

    assert session.get.call_count == 3


def test_non_recaptcha_406_raises_parse_error(monkeypatch):
    session = Mock()
    session.get.return_value = make_response(
        406, {"message": "some other validation error", "statusCode": 406}
    )
    client = make_client_with_session(session)

    monkeypatch.setattr(client, "_build_seo_key", lambda *a, **k: "seo-key")

    with pytest.raises(NaukriParseError):
        client.search_jobs(keyword="AI Engineer", location="Pune", page=1)

    assert session.get.call_count == 1
