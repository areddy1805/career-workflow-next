from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.models.models import Job
from src.search.job_cache_codec import JobCacheCodec

logger = logging.getLogger(__name__)


class JobSearchCache:
    SCHEMA_VERSION = 2
    SUPPORTED_VERSIONS = {1, 2}

    def __init__(
        self,
        path: str | Path = "data/job_search_cache.json",
        ttl_days: int = 3,
        now_fn: Callable[[], datetime] | None = None,
    ):
        self.path = Path(path)
        self.ttl = timedelta(days=ttl_days)
        self.now_fn = now_fn or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self.now_fn()

        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        return now.astimezone(UTC)

    def _parse_timestamp(
        self,
        value,
    ) -> datetime | None:
        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    def _is_fresh(
        self,
        cached_at: datetime,
    ) -> bool:
        age = self._now() - cached_at

        return age <= self.ttl

    def load(
        self,
    ) -> list[Job]:
        if not self.path.exists():
            return []

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            logger.warning(
                "Ignoring unreadable job cache: path=%s error=%s",
                self.path,
                exc,
            )

            return []

        if not isinstance(payload, dict):
            return []

        version = payload.get(
            "version",
            1,
        )

        if version not in self.SUPPORTED_VERSIONS:
            logger.warning(
                "Ignoring unsupported job cache schema: " "path=%s version=%s",
                self.path,
                version,
            )

            return []

        entries = payload.get("jobs") or []

        if not isinstance(entries, list):
            return []

        valid_jobs: list[Job] = []

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            cached_at = self._parse_timestamp(entry.get("cached_at"))

            if cached_at is None:
                continue

            if not self._is_fresh(cached_at):
                continue

            raw_job = entry.get("job")

            try:
                job = JobCacheCodec.deserialize(raw_job)
            except (
                TypeError,
                ValueError,
            ):
                continue

            setattr(
                job,
                "_cached_at",
                cached_at,
            )

            valid_jobs.append(job)

        return valid_jobs

    def save(
        self,
        jobs: list[Job],
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        now = self._now()

        entries = []

        for job in jobs:
            cached_at = getattr(
                job,
                "_cached_at",
                None,
            )

            if not isinstance(
                cached_at,
                datetime,
            ):
                cached_at = now

            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(
                    tzinfo=UTC,
                )

            entries.append(
                {
                    "cached_at": (cached_at.astimezone(UTC).isoformat()),
                    "job": JobCacheCodec.serialize(job),
                }
            )

        payload = {
            "version": self.SCHEMA_VERSION,
            "jobs": entries,
        }

        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")

        try:
            temp_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
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

    def merge(
        self,
        fresh_jobs: list[Job],
        cached_jobs: list[Job],
    ) -> list[Job]:
        """
        Merge fresh and cached jobs.

        Rules:
            - fresh jobs are emitted first
            - fresh jobs win duplicate conflicts
            - cache-only jobs follow
            - duplicate cached jobs are removed
            - original cache timestamps survive
        """

        merged: list[Job] = []
        seen_ids: set[str] = set()

        for job in fresh_jobs:
            job_id = str(job.job_id).strip()

            if not job_id:
                continue

            if job_id in seen_ids:
                continue

            seen_ids.add(job_id)

            # A live observation refreshes this job.
            if hasattr(job, "_cached_at"):
                delattr(
                    job,
                    "_cached_at",
                )

            merged.append(job)

        for job in cached_jobs:
            job_id = str(job.job_id).strip()

            if not job_id:
                continue

            if job_id in seen_ids:
                continue

            seen_ids.add(job_id)
            merged.append(job)

        return merged
