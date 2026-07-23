from types import SimpleNamespace

from src.application.diversity import (
    DiversityPolicy,
    diversify_jobs,
    normalize_role_family,
)


def j(i, title, company, location="Pune"):
    return SimpleNamespace(
        job_id=str(i), title=title, company=company, location=location
    )


def test_role_family_normalization():
    assert normalize_role_family("Senior AI Engineer") == normalize_role_family(
        "AI Engineer"
    )


def test_diversity_limits_shape_order_but_do_not_drop_unique_jobs():
    jobs = [
        j(1, "Senior AI Engineer", "A"),
        j(2, "AI Engineer", "A", "Remote"),
        j(3, "LLM Engineer", "A"),
        j(4, "AI Engineer", "B"),
    ]
    result = diversify_jobs(
        jobs,
        policy=DiversityPolicy(
            max_per_company_per_run=2, max_per_role_family_per_company=1
        ),
    )
    assert [x.job_id for x in result] == ["1", "3", "4", "2"]


def test_unseen_companies_are_prioritized():
    jobs = [j(1, "AI Engineer", "Seen"), j(2, "AI Engineer", "New")]
    result = diversify_jobs(jobs, historical_company_counts={"seen": 4})
    assert result[0].company == "New"
