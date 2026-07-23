from src.application.failure import (
    FailureKind,
    classify_application_exception,
)


class HTTPError(Exception):
    def __init__(
        self,
        status_code: int,
    ):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def test_429_is_retryable_safe() -> None:
    failure = classify_application_exception(HTTPError(429))

    assert failure.kind == FailureKind.RETRYABLE_SAFE
    assert failure.retryable is True


def test_500_is_retryable_safe() -> None:
    failure = classify_application_exception(HTTPError(500))

    assert failure.kind == FailureKind.RETRYABLE_SAFE
    assert failure.retryable is True


def test_503_is_retryable_safe() -> None:
    failure = classify_application_exception(HTTPError(503))

    assert failure.kind == FailureKind.RETRYABLE_SAFE
    assert failure.retryable is True


def test_connection_refused_is_retryable_safe() -> None:
    failure = classify_application_exception(
        ConnectionRefusedError("connection refused")
    )

    assert failure.kind == FailureKind.RETRYABLE_SAFE
    assert failure.retryable is True


def test_timeout_is_ambiguous() -> None:
    failure = classify_application_exception(TimeoutError("request timed out"))

    assert failure.kind == FailureKind.AMBIGUOUS_COMMIT
    assert failure.retryable is False


def test_connection_reset_is_ambiguous() -> None:
    failure = classify_application_exception(ConnectionResetError("connection reset"))

    assert failure.kind == FailureKind.AMBIGUOUS_COMMIT
    assert failure.retryable is False


def test_value_error_is_permanent() -> None:
    failure = classify_application_exception(ValueError("invalid application data"))

    assert failure.kind == FailureKind.PERMANENT
    assert failure.retryable is False


def test_unknown_exception_defaults_to_ambiguous() -> None:
    failure = classify_application_exception(RuntimeError("unknown failure"))

    assert failure.kind == FailureKind.AMBIGUOUS_COMMIT
    assert failure.retryable is False
