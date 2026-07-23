from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUEUE_STATUSES = (
    "PENDING",
    "IN_PROGRESS",
    "APPLIED",
    "SKIPPED",
    "EXPIRED",
)


class ManualActionQueue:
    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8",
                )
            )
        except (
            json.JSONDecodeError,
            OSError,
        ):
            return []

        return payload if isinstance(payload, list) else []

    def _save(
        self,
        rows: list[dict],
    ) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")

        temporary.write_text(
            json.dumps(
                rows,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temporary.replace(self.path)

    @staticmethod
    def _value(
        job: Any,
        key: str,
        default=None,
    ):
        if isinstance(job, dict):
            return job.get(
                key,
                default,
            )

        return getattr(
            job,
            key,
            default,
        )

    def list(
        self,
        *,
        status: str | None = None,
    ) -> list[dict]:
        rows = self._load()

        if status is None:
            return rows

        wanted = status.upper()

        return [
            row
            for row in rows
            if str(
                row.get(
                    "status",
                    "PENDING",
                )
            ).upper()
            == wanted
        ]

    def update_status(
        self,
        job_id: str,
        status: str,
        *,
        note: str = "",
    ) -> bool:
        status = status.upper()

        if status not in QUEUE_STATUSES:
            raise ValueError(f"Unsupported queue status: {status}")

        rows = self._load()
        now = datetime.now(timezone.utc).isoformat()
        updated = False

        for row in rows:
            if str(row.get("job_id")) != str(job_id):
                continue

            row["status"] = status
            row["updated_at"] = now

            if note:
                row["note"] = note

            if status == "APPLIED":
                row["applied_at"] = row.get("applied_at") or now

            updated = True
            break

        if updated:
            self._save(rows)

        return updated

    def _enqueue(
        self,
        *,
        job: Any,
        score: int,
        reason: str,
        source: str,
        run_id: str,
    ) -> bool:
        rows = self._load()

        job_id = str(
            self._value(
                job,
                "job_id",
                "",
            )
            or ""
        )

        if not job_id:
            return False

        now = datetime.now(timezone.utc).isoformat()

        title = str(
            self._value(
                job,
                "title",
                "",
            )
            or ""
        )

        company = str(
            self._value(
                job,
                "company",
                "",
            )
            or ""
        )

        url = str(
            self._value(
                job,
                "url",
                "",
            )
            or self._value(
                job,
                "job_url",
                "",
            )
            or ""
        )

        if not url:
            url = "https://www.naukri.com/" f"job-listings-{job_id}"

        for row in rows:
            if str(row.get("job_id")) != job_id:
                continue

            changed = False

            repair_values = {
                "title": title,
                "company": company,
                "url": url,
                "score": int(score or 0),
                "reason": reason,
                "source": source,
                "run_id": run_id,
            }

            for key, value in repair_values.items():
                current = row.get(key)

                if current in (
                    None,
                    "",
                ) and value not in (
                    None,
                    "",
                ):
                    row[key] = value
                    changed = True

            if changed:
                row["updated_at"] = now
                self._save(rows)

            return False

        rows.append(
            {
                "job_id": job_id,
                "title": title,
                "company": company,
                "url": url,
                "score": int(score or 0),
                "reason": reason,
                "source": source,
                "status": "PENDING",
                "run_id": run_id,
                "created_at": now,
                "updated_at": now,
                "applied_at": None,
            }
        )

        self._save(rows)

        return True

    def enqueue_external_apply(
        self,
        *,
        job: Any,
        score: int,
        reason: str = "",
        run_id: str = "",
    ) -> bool:
        return self._enqueue(
            job=job,
            score=score,
            reason=reason,
            source="external_apply",
            run_id=run_id,
        )

    def enqueue_manual_review(
        self,
        *,
        job: Any,
        score: int,
        reason: str = "",
        run_id: str = "",
    ) -> bool:
        return self._enqueue(
            job=job,
            score=score,
            reason=reason,
            source="manual_review",
            run_id=run_id,
        )
