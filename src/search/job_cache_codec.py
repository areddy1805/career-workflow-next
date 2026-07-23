from __future__ import annotations

from typing import Any

from src.models.models import Job


class JobCacheCodec:
    REQUIRED_FIELDS = {
        "job_id",
        "title",
        "company",
        "location",
        "experience",
        "salary",
        "posted_date",
        "posted_date",
    }

    @classmethod
    def serialize(
        cls,
        job: Job,
    ) -> dict[str, Any]:
        if not isinstance(job, Job):
            raise TypeError(f"Expected Job, got {type(job).__name__}")

        return {
            "job_id": job.job_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "experience": job.experience,
            "salary": job.salary,
            "posted_date": job.posted_date,
            "apply_url": job.apply_url,
            "description": job.description,
            "tags": list(job.tags),
            "acquisition_source": getattr(
                job,
                "acquisition_source",
                "unknown",
            ),
            "provider_id": getattr(job, "provider_id", "unknown"),
            "provider_name": getattr(job, "provider_name", "unknown"),
            "provider_source": getattr(job, "provider_source", "unknown"),
            "provider_job_id": getattr(job, "provider_job_id", ""),
        }

    @classmethod
    def deserialize(
        cls,
        payload: dict[str, Any],
    ) -> Job:
        if not isinstance(payload, dict):
            raise TypeError(f"Expected dict, got {type(payload).__name__}")

        missing = cls.REQUIRED_FIELDS - payload.keys()

        if missing:
            raise ValueError(
                "Cached job missing required fields: " + ", ".join(sorted(missing))
            )

        tags = payload.get("tags") or []

        if not isinstance(tags, list):
            tags = [str(tags)]

        job = Job(
            job_id=str(payload["job_id"]),
            title=str(payload["title"]),
            company=str(payload["company"]),
            location=str(payload["location"]),
            experience=str(payload["experience"]),
            salary=str(payload["salary"]),
            posted_date=str(payload["posted_date"]),
            apply_url=str(payload.get("apply_url") or payload.get("apply_link") or ""),
            description=str(payload.get("description") or ""),
            tags=list(tags),
            provider_id=str(payload.get("provider_id") or "unknown"),
            provider_name=str(payload.get("provider_name") or "unknown"),
            provider_source=str(payload.get("provider_source") or "unknown"),
            provider_job_id=str(payload.get("provider_job_id") or ""),
        )

        setattr(
            job,
            "acquisition_source",
            str(payload.get("acquisition_source") or "cache"),
        )

        return job
