from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path


class SearchChallengeCooldown:
    SCHEMA_VERSION = 1

    def __init__(
        self,
        path: str | Path = "data/search_challenge_state.json",
        cooldown_minutes: int = 60,
        now_fn: Callable[[], datetime] | None = None,
    ):
        self.path = Path(path)

        self.cooldown = timedelta(
            minutes=cooldown_minutes,
        )

        self.now_fn = now_fn or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self.now_fn()

        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        return now.astimezone(UTC)

    def record_challenge(
        self,
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "version": self.SCHEMA_VERSION,
            "challenged_at": (self._now().isoformat()),
        }

        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")

        try:
            temp_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                ),
                encoding="utf-8",
            )

            temp_path.replace(self.path)

        except Exception:
            try:
                temp_path.unlink(
                    missing_ok=True,
                )
            except OSError:
                pass

            raise

    def challenged_at(
        self,
    ) -> datetime | None:
        if not self.path.exists():
            return None

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return None

        if not isinstance(payload, dict):
            return None

        raw = payload.get("challenged_at")

        if not raw:
            return None

        try:
            value = datetime.fromisoformat(str(raw))
        except (
            TypeError,
            ValueError,
        ):
            return None

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=UTC,
            )

        return value.astimezone(UTC)

    def is_active(
        self,
    ) -> bool:
        challenged_at = self.challenged_at()

        if challenged_at is None:
            return False

        elapsed = self._now() - challenged_at

        return elapsed < self.cooldown

    def remaining_seconds(
        self,
    ) -> int:
        challenged_at = self.challenged_at()

        if challenged_at is None:
            return 0

        remaining = challenged_at + self.cooldown - self._now()

        return max(
            0,
            int(remaining.total_seconds()),
        )

    def clear(
        self,
    ) -> None:
        self.path.unlink(
            missing_ok=True,
        )
