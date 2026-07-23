import pytest
from src.models.models import Job
from src.application.models import RoutingStrategy, ATSType
from src.application.capability import ProviderCapabilities
from src.application.result import RoutingResult
from src.application.detector import ATSDetector
from src.application.router import ApplicationRouter


class TestATSDetector:
    def test_greenhouse(self):
        assert (
            ATSDetector.detect_from_url("https://boards.greenhouse.io/company/jobs/123")
            == ATSType.GREENHOUSE
        )

    def test_lever(self):
        assert (
            ATSDetector.detect_from_url("https://jobs.lever.co/company/123")
            == ATSType.LEVER
        )

    def test_workday(self):
        assert (
            ATSDetector.detect_from_url(
                "https://company.myworkdayjobs.com/en-US/Careers"
            )
            == ATSType.WORKDAY
        )

    def test_ashby(self):
        assert (
            ATSDetector.detect_from_url("https://jobs.ashbyhq.com/company/123")
            == ATSType.ASHBY
        )

    def test_smartrecruiters(self):
        assert (
            ATSDetector.detect_from_url("https://jobs.smartrecruiters.com/company/123")
            == ATSType.SMARTRECRUITERS
        )

    def test_oracle(self):
        assert (
            ATSDetector.detect_from_url(
                "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/careers"
            )
            == ATSType.ORACLE
        )

    def test_sap(self):
        assert (
            ATSDetector.detect_from_url("https://career5.successfactors.com/career")
            == ATSType.SAP
        )
        assert (
            ATSDetector.detect_from_url("https://jobs.sapsf.com/career") == ATSType.SAP
        )

    def test_unknown(self):
        assert (
            ATSDetector.detect_from_url("https://some-random-site.com/jobs/123")
            == ATSType.UNKNOWN
        )
        assert ATSDetector.detect_from_url(None) == ATSType.UNKNOWN
        assert ATSDetector.detect_from_url("") == ATSType.UNKNOWN


class TestApplicationRouter:
    @pytest.fixture
    def basic_job(self):
        return Job(
            job_id="123",
            title="Software Engineer",
            company="Tech Corp",
            location="Remote",
            experience="3-5",
            salary="100k",
            posted_date="2023-01-01",
            apply_url="https://naukri.com/apply/123",
        )

    def test_native_apply(self, basic_job):
        caps = ProviderCapabilities(
            native_apply=True,
            returns_external_url=False,
            requires_authentication=True,
            supports_resume_upload=True,
            supports_questionnaires=True,
        )

        result = ApplicationRouter.route(basic_job, caps)
        assert result.strategy == RoutingStrategy.NATIVE_APPLY

    def test_native_apply_with_external_override(self, basic_job):
        caps = ProviderCapabilities(
            native_apply=True,
            returns_external_url=True,
            requires_authentication=True,
            supports_resume_upload=True,
            supports_questionnaires=True,
        )

        # Although it supports native apply, we explicitly pass an external URL
        result = ApplicationRouter.route(
            basic_job, caps, "https://boards.greenhouse.io/techcorp/jobs/123"
        )
        assert result.strategy == RoutingStrategy.EXTERNAL_ATS
        assert result.ats_type == ATSType.GREENHOUSE

    def test_external_ats(self, basic_job):
        caps = ProviderCapabilities(
            native_apply=False,
            returns_external_url=True,
            requires_authentication=False,
            supports_resume_upload=False,
            supports_questionnaires=False,
        )
        basic_job.apply_url = "https://jobs.lever.co/techcorp/123"

        result = ApplicationRouter.route(basic_job, caps)
        assert result.strategy == RoutingStrategy.EXTERNAL_ATS
        assert result.ats_type == ATSType.LEVER

    def test_generic_career_site(self, basic_job):
        caps = ProviderCapabilities(
            native_apply=False,
            returns_external_url=True,
            requires_authentication=False,
            supports_resume_upload=False,
            supports_questionnaires=False,
        )
        basic_job.apply_url = "https://techcorp.com/careers/123"

        result = ApplicationRouter.route(basic_job, caps)
        assert result.strategy == RoutingStrategy.GENERIC_CAREER_SITE
        assert result.ats_type == ATSType.UNKNOWN

    def test_manual_review_unknown_site(self, basic_job):
        caps = ProviderCapabilities(
            native_apply=False,
            returns_external_url=True,
            requires_authentication=False,
            supports_resume_upload=False,
            supports_questionnaires=False,
        )
        basic_job.apply_url = (
            "https://techcorp.com/apply/123"  # missing "careers" or "jobs"
        )

        result = ApplicationRouter.route(basic_job, caps)
        assert result.strategy == RoutingStrategy.MANUAL_REVIEW
        assert result.ats_type == ATSType.UNKNOWN

    def test_manual_review_no_url(self, basic_job):
        caps = ProviderCapabilities(
            native_apply=False,
            returns_external_url=False,
            requires_authentication=False,
            supports_resume_upload=False,
            supports_questionnaires=False,
        )
        basic_job.apply_url = None

        result = ApplicationRouter.route(basic_job, caps)
        assert result.strategy == RoutingStrategy.MANUAL_REVIEW
