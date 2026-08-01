"""Tests for the Opportunity Lifecycle (Phase 1 of Application Orchestrator V2)."""

from datetime import datetime, timezone, timedelta
from src.orchestration.lifecycle import (
    OpportunityStatus,
    POOL_STATES,
    TERMINAL_STATES,
    PIPELINE_STATES,
    is_valid_transition,
)
from src.orchestration.explanation import DecisionExplanation
from src.orchestration.opportunity import ApplicationOpportunity


class TestOpportunityStatus:
    """Verify the lifecycle enum."""

    def test_all_statuses_defined(self):
        assert len(OpportunityStatus) == 9
        assert OpportunityStatus.DISCOVERED.value == "DISCOVERED"
        assert OpportunityStatus.CLASSIFIED.value == "CLASSIFIED"
        assert OpportunityStatus.SCORED.value == "SCORED"
        assert OpportunityStatus.ELIGIBLE.value == "ELIGIBLE"
        assert OpportunityStatus.PLANNED.value == "PLANNED"
        assert OpportunityStatus.APPLYING.value == "APPLYING"
        assert OpportunityStatus.APPLIED.value == "APPLIED"
        assert OpportunityStatus.DEFERRED_QUOTA.value == "DEFERRED_QUOTA"
        assert OpportunityStatus.EXPIRED.value == "EXPIRED"

    def test_pool_states(self):
        assert OpportunityStatus.SCORED in POOL_STATES
        assert OpportunityStatus.ELIGIBLE in POOL_STATES
        assert OpportunityStatus.DEFERRED_QUOTA in POOL_STATES
        assert OpportunityStatus.APPLIED not in POOL_STATES
        assert OpportunityStatus.EXPIRED not in POOL_STATES
        assert len(POOL_STATES) == 3

    def test_terminal_states(self):
        assert OpportunityStatus.APPLIED in TERMINAL_STATES
        assert OpportunityStatus.EXPIRED in TERMINAL_STATES
        assert OpportunityStatus.DEFERRED_QUOTA not in TERMINAL_STATES
        assert len(TERMINAL_STATES) == 2

    def test_pipeline_states(self):
        assert OpportunityStatus.DISCOVERED in PIPELINE_STATES
        assert OpportunityStatus.APPLIED in PIPELINE_STATES
        assert OpportunityStatus.DEFERRED_QUOTA not in PIPELINE_STATES
        assert OpportunityStatus.EXPIRED not in PIPELINE_STATES


class TestValidTransitions:
    """Verify state machine transition rules."""

    def test_none_to_discovered(self):
        assert is_valid_transition(None, OpportunityStatus.DISCOVERED)

    def test_none_to_anything_else(self):
        assert not is_valid_transition(None, OpportunityStatus.APPLIED)
        assert not is_valid_transition(None, OpportunityStatus.EXPIRED)

    def test_discovered_transitions(self):
        assert is_valid_transition(OpportunityStatus.DISCOVERED, OpportunityStatus.CLASSIFIED)

    def test_classified_transitions(self):
        assert is_valid_transition(OpportunityStatus.CLASSIFIED, OpportunityStatus.SCORED)

    def test_scored_transitions(self):
        assert is_valid_transition(OpportunityStatus.SCORED, OpportunityStatus.ELIGIBLE)
        assert is_valid_transition(OpportunityStatus.SCORED, OpportunityStatus.DEFERRED_QUOTA)
        assert is_valid_transition(OpportunityStatus.SCORED, OpportunityStatus.EXPIRED)

    def test_eligible_transitions(self):
        assert is_valid_transition(OpportunityStatus.ELIGIBLE, OpportunityStatus.PLANNED)
        assert is_valid_transition(OpportunityStatus.ELIGIBLE, OpportunityStatus.DEFERRED_QUOTA)

    def test_planned_transitions(self):
        assert is_valid_transition(OpportunityStatus.PLANNED, OpportunityStatus.APPLYING)
        assert is_valid_transition(OpportunityStatus.PLANNED, OpportunityStatus.DEFERRED_QUOTA)

    def test_applying_transitions(self):
        assert is_valid_transition(OpportunityStatus.APPLYING, OpportunityStatus.APPLIED)
        assert is_valid_transition(OpportunityStatus.APPLYING, OpportunityStatus.DEFERRED_QUOTA)
        assert is_valid_transition(OpportunityStatus.APPLYING, OpportunityStatus.SCORED)

    def test_deferred_transitions(self):
        assert is_valid_transition(OpportunityStatus.DEFERRED_QUOTA, OpportunityStatus.PLANNED)
        assert is_valid_transition(OpportunityStatus.DEFERRED_QUOTA, OpportunityStatus.EXPIRED)

    def test_terminal_states_are_final(self):
        assert not is_valid_transition(OpportunityStatus.APPLIED, OpportunityStatus.SCORED)
        assert not is_valid_transition(OpportunityStatus.APPLIED, OpportunityStatus.DEFERRED_QUOTA)
        assert not is_valid_transition(OpportunityStatus.APPLIED, OpportunityStatus.PLANNED)
        assert not is_valid_transition(OpportunityStatus.EXPIRED, OpportunityStatus.SCORED)
        assert not is_valid_transition(OpportunityStatus.EXPIRED, OpportunityStatus.DEFERRED_QUOTA)

    def test_invalid_transitions(self):
        assert not is_valid_transition(OpportunityStatus.DISCOVERED, OpportunityStatus.APPLIED)
        assert not is_valid_transition(OpportunityStatus.CLASSIFIED, OpportunityStatus.APPLIED)
        assert not is_valid_transition(OpportunityStatus.ELIGIBLE, OpportunityStatus.APPLIED)
        assert not is_valid_transition(OpportunityStatus.DEFERRED_QUOTA, OpportunityStatus.APPLIED)


class TestDecisionExplanation:
    """Verify the DecisionExplanation dataclass."""

    def test_applied_factory(self):
        d = DecisionExplanation.applied_factory(95.0, {"base": 95, "semantic": 0}, "Score 95")
        assert d.final_score == 95.0
        assert d.applied is True
        assert d.deferred_reason == ""
        assert d.summary == "Score 95"

    def test_deferred_factory(self):
        d = DecisionExplanation.deferred(85.0, "Quota exhausted at rank 61")
        assert d.final_score == 85.0
        assert d.applied is False
        assert d.deferred_reason == "Quota exhausted at rank 61"

    def test_to_dict(self):
        d = DecisionExplanation.applied_factory(97.3, {"base": 95, "freshness": 1.0, "semantic": 2.3}, "Score 97.3")
        data = d.to_dict()
        assert data["final_score"] == 97.3
        assert data["applied"] is True
        assert data["components"]["base"] == 95.0
        assert data["components"]["semantic"] == 2.3
        assert "summary" in data

    def test_defaults(self):
        d = DecisionExplanation()
        assert d.final_score == 0.0
        assert d.applied is False
        assert d.components == {}


class TestApplicationOpportunity:
    """Verify the ApplicationOpportunity dataclass."""

    def test_default_values(self):
        opp = ApplicationOpportunity()
        assert opp.status == "DISCOVERED"
        assert opp.resume_profile == "generic"
        assert opp.score == 0.0
        assert opp.is_external is False

    def test_to_dict(self):
        opp = ApplicationOpportunity(
            job_id="123",
            provider_id="naukri",
            title="Software Engineer",
            company="Google",
            score=95.0,
            status="SCORED",
        )
        data = opp.to_dict()
        assert data["job_id"] == "123"
        assert data["provider_id"] == "naukri"
        assert data["title"] == "Software Engineer"
        assert data["company"] == "Google"
        assert data["score"] == 95.0
        assert data["status"] == "SCORED"
        assert data["is_external"] is False
        assert "acquired_at" in data
        assert "last_evaluated" in data

    def test_from_job_minimal(self):
        """Test from_job with a minimal mock job."""
        class MockJob:
            job_id = "456"
            provider_id = "naukri"
            title = "Data Scientist"
            company = "Meta"
            score = 88.0
            tags = ["ai", "machine learning"]
            acquired_at = datetime.now(timezone.utc) - timedelta(days=2)
            apply_url = None
            is_external_apply = False

        opp = ApplicationOpportunity.from_job(MockJob(), status="SCORED")
        assert opp.job_id == "456"
        assert opp.provider_id == "naukri"
        assert opp.title == "Data Scientist"
        assert opp.company == "Meta"
        assert opp.score == 88.0
        assert opp.status == "SCORED"
        assert opp.resume_profile == "AI"  # Based on tags
        assert opp.age_days > 0

    def test_from_job_no_tags(self):
        """Test from_job with no tags (should default to FDE)."""
        class MockJob:
            job_id = "789"
            provider_id = "hiringcafe"
            title = "Accountant"
            company = "Deloitte"
            score = 75.0
            tags = []

        opp = ApplicationOpportunity.from_job(MockJob())
        assert opp.resume_profile == "FDE"  # No AI keywords
        assert opp.job_id == "789"
        assert opp.provider_id == "hiringcafe"
