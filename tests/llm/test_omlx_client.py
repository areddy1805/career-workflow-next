import httpx
import pytest

from src.llm.client import OMLXClient, OMLXClientError


class FakeResponse:
    def __init__(
        self,
        payload: dict,
        *,
        status_code: int = 200,
    ):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request(
                "GET",
                "http://test.local",
            )
            response = httpx.Response(
                self.status_code,
                request=request,
            )
            raise httpx.HTTPStatusError(
                "request failed",
                request=request,
                response=response,
            )

    def json(self) -> dict:
        return self.payload


def test_health_check_returns_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(*args, **kwargs):
        return FakeResponse(
            {
                "data": [
                    {"id": "other-model"},
                    {"id": "test-model"},
                ]
            }
        )

    monkeypatch.setattr(
        httpx.Client,
        "get",
        fake_get,
    )

    client = OMLXClient(
        base_url="http://test.local/v1",
        model="test-model",
    )

    result = client.health_check()

    assert result == {
        "status": "ok",
        "model": "test-model",
        "available_models": [
            "other-model",
            "test-model",
        ],
    }


def test_health_check_rejects_missing_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(*args, **kwargs):
        return FakeResponse(
            {
                "data": [
                    {"id": "other-model"},
                ]
            }
        )

    monkeypatch.setattr(
        httpx.Client,
        "get",
        fake_get,
    )

    client = OMLXClient(
        base_url="http://test.local/v1",
        model="test-model",
    )

    with pytest.raises(
        OMLXClientError,
        match="Configured model 'test-model' is unavailable",
    ):
        client.health_check()


def test_chat_returns_completion_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(*args, **kwargs):
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "capability",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(
        httpx.Client,
        "post",
        fake_post,
    )

    client = OMLXClient(
        base_url="http://test.local/v1",
        model="test-model",
    )

    response = client.chat(
        messages=[
            {
                "role": "user",
                "content": ("Have you built FastAPI-based " "model serving APIs?"),
            }
        ],
        temperature=0.0,
        max_tokens=100,
    )

    assert response == "capability"


def test_chat_rejects_unexpected_response_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(*args, **kwargs):
        return FakeResponse(
            {
                "unexpected": "response",
            }
        )

    monkeypatch.setattr(
        httpx.Client,
        "post",
        fake_post,
    )

    client = OMLXClient(
        base_url="http://test.local/v1",
        model="test-model",
    )

    with pytest.raises(
        OMLXClientError,
        match="Unexpected oMLX response structure",
    ):
        client.chat(
            messages=[
                {
                    "role": "user",
                    "content": "test",
                }
            ]
        )
