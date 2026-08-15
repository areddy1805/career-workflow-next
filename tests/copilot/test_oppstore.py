"""Unit tests for CP-1-10: CopilotOpportunity model, serialization, fingerprint."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from src.copilot.constants import (
    ApplicationStrategy,
    OpportunitySource,
    OpportunityStatusView,
    Provenance,
)
from src.copilot.exceptions import CopilotError
from src.copilot.oppstore.model import (
    Attachment,
    CopilotOpportunity,
    EffortEstimate,
    ResumeRec,
    _exp_bucket,
    _normalize,
)


def full_opportunity(**overrides) -> CopilotOpportunity:
    fields = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title="Senior Backend Engineer",
        company="Acme Corp",
        provider_id="acme",
        provider_job_id="job-42",
        source_url="https://acme.com/careers/42",
        canonical_url="https://acme.com/careers/42",
        seniority="senior",
        employment_type="full_time",
        work_mode="remote",
        experience_required="3-5 years",
        role_family="fullstack",
        company_domain="acme.com",
        company_size="51-200",
        industry="software",
        ats_type="greenhouse",
        careers_url="https://acme.com/careers",
        comp_min=150000.0,
        comp_max=180000.0,
        currency="USD",
        comp_notes="plus equity",
        equity="0.1%",
        bonus="10%",
        market_benchmark={"low": 140000, "median": 160000, "high": 190000},
        required_skills=["python", "sql"],
        preferred_skills=["kubernetes"],
        tools=["aws"],
        domain_knowledge=["fintech"],
        city="San Francisco",
        region="CA",
        country="US",
        remote=True,
        relocation_required=False,
        apply_url="https://boards.greenhouse.io/acme/jobs/42",
        application_strategy=ApplicationStrategy.ATS.value,
        attachments=[Attachment(name="job.pdf", kind="pdf", ref="f1")],
        resume_recommendation=ResumeRec(
            resume_type="technical", reason="match", scores={"fit": 0.9}
        ),
        description_html="<p>Role</p>",
        description_text="Role description",
        raw_ref="https://acme.com/careers/42",
        acquired_at=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
        provenance={"title": [Provenance.PARSER.value]},
        confidence={"title": 0.99},
        score=0.8,
        fit_class="strong",
        missing_skills=["rust"],
        interview_probability=0.4,
        effort_estimate=EffortEstimate(
            fields=12, pages=1, ats_type="greenhouse",
            auto_fillable_frac=0.8, minutes=15,
        ),
        status_view=OpportunityStatusView.NEW.value,
    )
    fields.update(overrides)
    return CopilotOpportunity(**fields)


def minimal_opportunity(**overrides) -> CopilotOpportunity:
    fields = dict(
        source=OpportunitySource.MANUAL_QUEUE.value,
        title="Backend Engineer",
        company="Acme Corp",
    )
    fields.update(overrides)
    return CopilotOpportunity(**fields)


# ------------------------------------------------------------ serialization


def test_to_dict_from_dict_round_trip():
    opp = full_opportunity()
    assert CopilotOpportunity.from_dict(opp.to_dict()) == opp


def test_round_trip_with_minimal_fields():
    opp = minimal_opportunity()
    assert CopilotOpportunity.from_dict(opp.to_dict()) == opp


def test_to_dict_is_json_safe():
    import json

    data = full_opportunity().to_dict()
    json.dumps(data)  # must not raise


def test_from_dict_missing_required_raises():
    with pytest.raises(CopilotError, match="required"):
        CopilotOpportunity.from_dict({"source": "manual_queue", "title": "x"})


def test_from_dict_ignores_unknown_keys():
    opp = minimal_opportunity()
    data = opp.to_dict()
    data["future_field"] = "ignored"
    assert CopilotOpportunity.from_dict(data) == opp


def test_from_dict_missing_optional_fields_gets_defaults():
    opp = CopilotOpportunity.from_dict(
        {"source": "manual_queue", "title": "T", "company": "C"}
    )
    assert opp.required_skills == []
    assert opp.status_view == OpportunityStatusView.NEW.value
    assert opp.application_strategy == ApplicationStrategy.UNSUPPORTED.value


def test_acquired_at_serializes_iso_utc():
    opp = minimal_opportunity(
        acquired_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    )
    assert opp.to_dict()["acquired_at"].endswith("+00:00")
    assert CopilotOpportunity.from_dict(opp.to_dict()).acquired_at == opp.acquired_at


# ------------------------------------------------------------ fingerprint


def test_fingerprint_stable_across_instances():
    a = minimal_opportunity()
    b = minimal_opportunity()
    assert a.fingerprint == b.fingerprint
    assert len(a.fingerprint) == 16
    assert int(a.fingerprint, 16) >= 0  # hex


def test_fingerprint_changes_with_identity():
    base = minimal_opportunity()
    other_company = minimal_opportunity(company="Other Corp")
    other_title = minimal_opportunity(title="Frontend Engineer")
    assert base.fingerprint != other_company.fingerprint
    assert base.fingerprint != other_title.fingerprint


def test_fingerprint_ignores_non_identity_fields():
    a = minimal_opportunity()
    b = minimal_opportunity(description_text="completely different text")
    c = minimal_opportunity(comp_min=10.0)
    assert a.fingerprint == b.fingerprint == c.fingerprint


def test_fingerprint_uses_city_and_experience_bucket():
    a = minimal_opportunity(city="San Francisco", experience_required="3-5 years")
    b = minimal_opportunity(city="New York", experience_required="3-5 years")
    assert a.fingerprint != b.fingerprint
    assert a.fingerprint == minimal_opportunity(
        city="San Francisco", experience_required="4 years"
    ).fingerprint  # same bucket


def test_fingerprint_computed_when_missing():
    opp = minimal_opportunity()
    assert opp.fingerprint == opp.compute_fingerprint()


def test_fingerprint_preserved_when_provided():
    opp = minimal_opportunity(fingerprint="abc123")
    assert opp.fingerprint == "abc123"
    assert CopilotOpportunity.from_dict(opp.to_dict()).fingerprint == "abc123"


@pytest.mark.parametrize(
    ("value", "bucket"),
    [
        (None, "unknown"),
        ("", "unknown"),
        ("no experience needed", "unknown"),
        ("1+ years", "0-1"),
        ("3-5 years", "2-4"),
        ("6 years", "5+"),
        ("10+ years", "5+"),
    ],
)
def test_exp_bucket(value, bucket):
    assert _exp_bucket(value) == bucket


def test_normalize_collapses_whitespace_and_case():
    assert _normalize("  Senior\n  BACKEND  Engineer ") == "senior backend engineer"


# ------------------------------------------------------------ provenance


def test_provenance_enforced_unknown_field():
    with pytest.raises(CopilotError, match="unknown field"):
        minimal_opportunity(provenance={"nope": ["parser"]})


@pytest.mark.parametrize(
    "bad_sources",
    [["parser", "alien"], [], [Provenance.LLM.value, "guess"]],
)
def test_provenance_enforced_invalid_sources(bad_sources):
    with pytest.raises(CopilotError, match="Provenance"):
        minimal_opportunity(provenance={"title": bad_sources})


def test_provenance_valid_sources_accepted():
    opp = minimal_opportunity(
        provenance={"title": ["parser"], "company": ["provider", "human"]}
    )
    assert opp.provenance["company"] == ["provider", "human"]


# ------------------------------------------------------------ vocabulary


@pytest.mark.parametrize(
    "bad_source",
    ["nope", "linked in", OpportunitySource.FUTURE.value + "x"],
)
def test_source_enum_enforced(bad_source):
    with pytest.raises(CopilotError, match="source="):
        minimal_opportunity(source=bad_source)


def test_application_strategy_enum_enforced():
    with pytest.raises(CopilotError, match="application_strategy="):
        minimal_opportunity(application_strategy="auto-submit")


def test_status_view_enum_enforced():
    with pytest.raises(CopilotError, match="status_view="):
        minimal_opportunity(status_view="NOPE")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seniority", "principal"),
        ("employment_type", "freelance"),
        ("work_mode", "four_days_office"),
        ("role_family", "data_science"),
        ("ats_type", "smartrecruiters"),
        ("fit_class", "perfect"),
    ],
)
def test_optional_enum_fields_enforced(field, value):
    with pytest.raises(CopilotError, match=f"{field}="):
        minimal_opportunity(**{field: value})


# ------------------------------------------------------------ immutability


def test_opportunity_is_frozen():
    opp = minimal_opportunity()
    with pytest.raises(FrozenInstanceError):
        opp.title = "changed"


def test_sub_models_are_frozen():
    with pytest.raises(FrozenInstanceError):
        Attachment(name="a", kind="pdf", ref="r").name = "b"


# ------------------------------------------------------------ defaults


def test_defaults():
    opp = minimal_opportunity()
    assert opp.opportunity_id
    assert opp.provider_id == ""
    assert opp.acquired_at.tzinfo is not None
    assert opp.missing_skills == []
    assert opp.attachments == []
