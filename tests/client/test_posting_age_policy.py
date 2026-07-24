import pytest
from src.client.job_classifier import JobFilterPipeline2

@pytest.fixture
def classifier():
    return JobFilterPipeline2()

def test_posting_age_policy_5_days(classifier, monkeypatch):
    monkeypatch.setenv("SEARCH_STRATEGY_CONFIG", "config/search_strategy.yaml")
    jobs = [{"title": "Software Engineer", "posted_date": "5 days ago", "provider_name": "indeed", "company": "Test Co"}]
    result = classifier.pre_filter(jobs)
    assert len(result) == 1
    assert result[0]["days_old"] == 5
    assert not any(d.get("rejection_code") == "POSTING_TOO_OLD" for d in classifier.rejected_jobs)

def test_posting_age_policy_29_days(classifier, monkeypatch):
    monkeypatch.setenv("SEARCH_STRATEGY_CONFIG", "config/search_strategy.yaml")
    jobs = [{"title": "Software Engineer", "posted_date": "29 days ago", "provider_name": "indeed", "company": "Test Co"}]
    result = classifier.pre_filter(jobs)
    assert len(result) == 1
    assert result[0]["days_old"] == 29

def test_posting_age_policy_exactly_30_days(classifier, monkeypatch):
    monkeypatch.setenv("SEARCH_STRATEGY_CONFIG", "config/search_strategy.yaml")
    jobs = [{"title": "Software Engineer", "posted_date": "30 days ago", "provider_name": "indeed", "company": "Test Co"}]
    result = classifier.pre_filter(jobs)
    assert len(result) == 1
    assert result[0]["days_old"] == 30

def test_posting_age_policy_31_days(classifier, monkeypatch):
    monkeypatch.setenv("SEARCH_STRATEGY_CONFIG", "config/search_strategy.yaml")
    jobs = [{"title": "Software Engineer", "posted_date": "31 days ago", "provider_name": "indeed", "company": "Test Co"}]
    result = classifier.pre_filter(jobs)
    assert len(result) == 0
    assert len(classifier.rejected_jobs) == 1
    assert classifier.rejected_jobs[0]["rejection_code"] == "POSTING_TOO_OLD"
    assert "Threshold: 30" in classifier.rejected_jobs[0]["rejection_reason"]

def test_posting_age_policy_unknown_date(classifier, monkeypatch):
    monkeypatch.setenv("SEARCH_STRATEGY_CONFIG", "config/search_strategy.yaml")
    jobs = [{"title": "Software Engineer", "provider_name": "indeed", "company": "Test Co"}]
    result = classifier.pre_filter(jobs)
    assert len(result) == 1
    assert result[0].get("days_old") is None

def test_posting_age_policy_malformed_date(classifier, monkeypatch):
    monkeypatch.setenv("SEARCH_STRATEGY_CONFIG", "config/search_strategy.yaml")
    jobs = [{"title": "Software Engineer", "posted_date": "some weird date", "provider_name": "indeed", "company": "Test Co"}]
    result = classifier.pre_filter(jobs)
    assert len(result) == 1
    assert result[0].get("days_old") is None

def test_posting_age_policy_provider_with_no_support(classifier, monkeypatch):
    # Testing with 'reject_unknown_posting_age' set to True
    from src.config.search_strategy import SearchStrategyConfig, JobPolicyConfig
    def mock_load():
        return SearchStrategyConfig(job_policy=JobPolicyConfig(max_posting_age_days=30, reject_unknown_posting_age=True))
    
    monkeypatch.setattr("src.config.search_strategy.load_search_strategy", mock_load)
    
    jobs = [{"title": "Software Engineer", "provider_name": "unsupported_provider", "company": "Test Co"}]
    result = classifier.pre_filter(jobs)
    assert len(result) == 0
    assert len(classifier.rejected_jobs) == 1
    assert classifier.rejected_jobs[0]["rejection_code"] == "POSTING_TOO_OLD"
    assert "Age: unknown" in classifier.rejected_jobs[0]["rejection_reason"]
