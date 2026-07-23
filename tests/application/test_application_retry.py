import pytest

from apply_agent import execute_with_safe_retry


class HTTPError(Exception):
    def __init__(
        self,
        status_code: int,
    ):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def test_success_returns_without_retry() -> None:
    calls = 0
    sleeps: list[int] = []

    def operation():
        nonlocal calls
        calls += 1
        return {"ok": True}

    result = execute_with_safe_retry(
        operation,
        sleep_fn=sleeps.append,
    )

    assert result == {"ok": True}
    assert calls == 1
    assert sleeps == []


def test_429_retries_then_succeeds() -> None:
    calls = 0
    sleeps: list[int] = []

    def operation():
        nonlocal calls
        calls += 1

        if calls < 3:
            raise HTTPError(429)

        return {"ok": True}

    result = execute_with_safe_retry(
        operation,
        max_retries=2,
        sleep_fn=sleeps.append,
    )

    assert result == {"ok": True}
    assert calls == 3
    assert sleeps == [1, 2]


def test_503_retries_then_succeeds() -> None:
    calls = 0
    sleeps: list[int] = []

    def operation():
        nonlocal calls
        calls += 1

        if calls == 1:
            raise HTTPError(503)

        return "success"

    result = execute_with_safe_retry(
        operation,
        max_retries=2,
        sleep_fn=sleeps.append,
    )

    assert result == "success"
    assert calls == 2
    assert sleeps == [1]


def test_retry_budget_is_bounded() -> None:
    calls = 0
    sleeps: list[int] = []

    def operation():
        nonlocal calls
        calls += 1
        raise HTTPError(500)

    with pytest.raises(HTTPError):
        execute_with_safe_retry(
            operation,
            max_retries=2,
            sleep_fn=sleeps.append,
        )

    assert calls == 3
    assert sleeps == [1, 2]


def test_timeout_is_not_retried() -> None:
    calls = 0
    sleeps: list[int] = []

    def operation():
        nonlocal calls
        calls += 1
        raise TimeoutError("timed out")

    with pytest.raises(TimeoutError):
        execute_with_safe_retry(
            operation,
            max_retries=2,
            sleep_fn=sleeps.append,
        )

    assert calls == 1
    assert sleeps == []


def test_connection_reset_is_not_retried() -> None:
    calls = 0
    sleeps: list[int] = []

    def operation():
        nonlocal calls
        calls += 1
        raise ConnectionResetError("reset")

    with pytest.raises(ConnectionResetError):
        execute_with_safe_retry(
            operation,
            max_retries=2,
            sleep_fn=sleeps.append,
        )

    assert calls == 1
    assert sleeps == []


def test_permanent_failure_is_not_retried() -> None:
    calls = 0
    sleeps: list[int] = []

    def operation():
        nonlocal calls
        calls += 1
        raise ValueError("invalid data")

    with pytest.raises(ValueError):
        execute_with_safe_retry(
            operation,
            max_retries=2,
            sleep_fn=sleeps.append,
        )

    assert calls == 1
    assert sleeps == []


def test_unknown_failure_is_not_retried() -> None:
    calls = 0
    sleeps: list[int] = []

    def operation():
        nonlocal calls
        calls += 1
        raise RuntimeError("unknown")

    with pytest.raises(RuntimeError):
        execute_with_safe_retry(
            operation,
            max_retries=2,
            sleep_fn=sleeps.append,
        )

    assert calls == 1
    assert sleeps == []
