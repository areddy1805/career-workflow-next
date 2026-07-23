from src.application.eligibility import evaluate_auto_apply_eligibility


def _job(title="AI Engineer", company="Test Co", job_id="1"):
    return {
        "job_id": job_id,
        "title": title,
        "company": company,
    }


def test_low_score_is_still_eligible():
    job = _job()
    score_map = {"1": {"score": 1, "reason": "weak stack match"}}

    decision = evaluate_auto_apply_eligibility(
        job,
        score_map=score_map,
        minimum_score=68,
    )

    assert decision["eligible"] is True
    assert decision["reasons"] == []


def test_junior_ai_role_is_still_eligible():
    job = _job(title="Junior AI Developer")
    score_map = {
        "1": {
            "score": 40,
            "reason": "severe seniority mismatch",
        }
    }

    decision = evaluate_auto_apply_eligibility(
        job,
        score_map=score_map,
    )

    assert decision["eligible"] is True


def test_incidental_ai_classification_does_not_reject():
    job = _job(title="Full Stack AI Engineer")
    score_map = {
        "1": {
            "score": 45,
            "reason": "AI aspect appears merely incidental",
        }
    }

    decision = evaluate_auto_apply_eligibility(
        job,
        score_map=score_map,
    )

    assert decision["eligible"] is True


def test_stack_mismatch_does_not_reject():
    job = _job(title="Computer Vision Engineer")
    score_map = {
        "1": {
            "score": 30,
            "reason": "significant stack mismatch",
        }
    }

    decision = evaluate_auto_apply_eligibility(
        job,
        score_map=score_map,
    )

    assert decision["eligible"] is True
