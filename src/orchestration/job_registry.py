import uuid
from typing import Any, Tuple


class JobRegistry:
    def __init__(self):
        self.jobs = {}

    def register(self, job: Any) -> str:
        is_dict = isinstance(job, dict)

        jid = (
            job.get("pipeline_job_id")
            if is_dict
            else getattr(job, "pipeline_job_id", None)
        )

        if not jid:
            jid = str(uuid.uuid4())
            if is_dict:
                job["pipeline_job_id"] = jid
            else:
                job.pipeline_job_id = jid

        if jid not in self.jobs:
            self.jobs[jid] = {"pipeline_job_id": jid}

        return jid

    def get_metadata(self, job: Any, extra: dict = None) -> Tuple[dict, str]:
        jid = self.register(job)

        is_dict = isinstance(job, dict)
        title = job.get("title", "") if is_dict else getattr(job, "title", "")
        company = job.get("company", "") if is_dict else getattr(job, "company", "")
        provider_id = job.get("job_id", "") if is_dict else getattr(job, "job_id", "")
        provider = (
            job.get("provider", "unknown")
            if is_dict
            else getattr(job, "provider", "unknown")
        )

        data = {
            "pipeline_job_id": jid,
            "provider": provider,
            "provider_job_id": provider_id,
            "title": title,
            "company": company,
        }

        if extra:
            data.update(extra)

        return data, jid
