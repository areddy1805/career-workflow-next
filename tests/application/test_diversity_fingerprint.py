from dataclasses import dataclass

from src.application.diversity import (
    DiversityPolicy,
    diversify_jobs,
    vacancy_fingerprint,
)


@dataclass
class Job:
    title: str
    company: str
    location: str


def test_vacancy_fingerprint_normalizes_equivalent_jobs():
    a = Job("Senior LLM Engineer", "Acme Pvt. Ltd.", "Pune")
    b = Job("LLM Engineer", "ACME PVT LTD", "Pune")
    assert vacancy_fingerprint(a) == vacancy_fingerprint(b)


def test_duplicate_vacancy_is_suppressed():
    jobs = [
        Job("Senior LLM Engineer", "Acme", "Pune"),
        Job("LLM Engineer", "Acme", "Pune"),
        Job("RAG Engineer", "Acme", "Pune"),
    ]
    result = diversify_jobs(
        jobs,
        policy=DiversityPolicy(
            max_per_company_per_run=3,
            max_per_role_family_per_company=2,
            max_per_vacancy_fingerprint=1,
        ),
    )
    assert len(result) == 2


from src.application.diversity import (
    deduplicate_enriched_jobs,
    exclude_job_ids,
)



def test_post_detail_description_dedup_removes_requisition_clones():
    jobs = [
        {
            "job_id": "1",
            "title": "LLM Model Developer",
            "company": "A",
            "location": "Pune",
            "description": "Build enterprise Agentic AI systems. Requisition ID 12345678",
        },
        {
            "job_id": "2",
            "title": "LLM Model Developer",
            "company": "A",
            "location": "Bengaluru",
            "description": "Build enterprise Agentic AI systems. Requisition ID 87654321",
        },
        {
            "job_id": "3",
            "title": "LLM Model Developer",
            "company": "A",
            "location": "Pune",
            "description": "Fine tune language models for domain adaptation.",
        },
    ]
    result = deduplicate_enriched_jobs(jobs)
    assert [job["job_id"] for job in result] == ["1", "3"]


def test_exclude_job_ids_before_detail_fetch():
    jobs = [{"job_id": "1"}, {"job_id": "2"}, {"job_id": "3"}]
    assert [j["job_id"] for j in exclude_job_ids(jobs, {"2"})] == ["1", "3"]



def test_vacancy_fingerprint_distinguishes_materially_different_search_metadata():
    a = {
        "title": "LLM Engineer",
        "company": "Acme",
        "location": "Pune",
        "experience": "3-5 Yrs",
        "tags": ["Python", "RAG"],
    }
    b = {
        "title": "LLM Engineer",
        "company": "Acme",
        "location": "Pune",
        "experience": "6-9 Yrs",
        "tags": ["Java", "Spring AI"],
    }
    assert vacancy_fingerprint(a) != vacancy_fingerprint(b)


def test_configured_vacancy_fingerprint_limit_is_honored():
    jobs = [
        Job("LLM Engineer", "Acme", "Pune"),
        Job("Senior LLM Engineer", "Acme", "Pune"),
        Job("LLM Engineer", "Acme", "Pune"),
    ]
    result = diversify_jobs(
        jobs,
        policy=DiversityPolicy(
            max_per_company_per_run=10,
            max_per_role_family_per_company=10,
            max_per_vacancy_fingerprint=2,
        ),
    )
    assert len(result) == 2
