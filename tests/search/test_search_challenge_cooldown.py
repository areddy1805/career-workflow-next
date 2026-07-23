from datetime import UTC, datetime, timedelta

from src.search.challenge_cooldown import (
    SearchChallengeCooldown,
)

BASE_TIME = datetime(
    2026,
    7,
    6,
    12,
    0,
    tzinfo=UTC,
)


class Clock:
    def __init__(
        self,
        value,
    ):
        self.value = value

    def now(
        self,
    ):
        return self.value


def test_missing_state_is_not_active(
    tmp_path,
):
    clock = Clock(BASE_TIME)

    cooldown = SearchChallengeCooldown(
        path=tmp_path / "state.json",
        cooldown_minutes=60,
        now_fn=clock.now,
    )

    assert cooldown.is_active() is False
    assert cooldown.remaining_seconds() == 0


def test_recorded_challenge_activates_cooldown(
    tmp_path,
):
    clock = Clock(BASE_TIME)

    cooldown = SearchChallengeCooldown(
        path=tmp_path / "state.json",
        cooldown_minutes=60,
        now_fn=clock.now,
    )

    cooldown.record_challenge()

    assert cooldown.is_active() is True
    assert cooldown.remaining_seconds() == 3600


def test_cooldown_expires(
    tmp_path,
):
    clock = Clock(BASE_TIME)

    cooldown = SearchChallengeCooldown(
        path=tmp_path / "state.json",
        cooldown_minutes=60,
        now_fn=clock.now,
    )

    cooldown.record_challenge()

    clock.value = BASE_TIME + timedelta(minutes=61)

    assert cooldown.is_active() is False
    assert cooldown.remaining_seconds() == 0


def test_corrupt_state_is_treated_as_inactive(
    tmp_path,
):
    path = tmp_path / "state.json"

    path.write_text(
        "{broken",
        encoding="utf-8",
    )

    cooldown = SearchChallengeCooldown(
        path=path,
        cooldown_minutes=60,
        now_fn=lambda: BASE_TIME,
    )

    assert cooldown.is_active() is False


def test_clear_removes_cooldown(
    tmp_path,
):
    cooldown = SearchChallengeCooldown(
        path=tmp_path / "state.json",
        cooldown_minutes=60,
        now_fn=lambda: BASE_TIME,
    )

    cooldown.record_challenge()

    assert cooldown.is_active() is True

    cooldown.clear()

    assert cooldown.is_active() is False
