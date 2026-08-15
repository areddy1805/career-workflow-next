"""Unit tests for CP-0-01: copilot package scaffold (enums + config)."""

import pytest
import yaml

from src.copilot import __version__
from src.copilot.config.loader import CopilotConfig, load_copilot_config
from src.copilot.constants import (
    AnswerSource,
    AnswerStatus,
    ApplicationStrategy,
    AtsType,
    EmploymentType,
    EventNamespace,
    FitClass,
    OpportunitySource,
    OpportunityStatusView,
    Provenance,
    RoleFamily,
    Seniority,
    SessionEventType,
    SessionState,
    WorkMode,
)
from src.copilot.exceptions import CopilotConfigurationError, CopilotError

# ---------------------------------------------------------------------------
# Frozen enum contracts (03_OPPORTUNITY_MODEL.md §2, 02_ARCHITECTURE.md §7,
# ADR-012). Exact value sets pin the interface freeze.
# ---------------------------------------------------------------------------


def test_source_enum_matches_frozen_contract():
    assert set(OpportunitySource) == {
        "manual_queue",
        "generic_url",
        "linkedin_url",
        "wellfound_url",
        "careers_url",
        "pasted_text",
        "pdf",
        "greenhouse",
        "lever",
        "ashby",
        "workday",
        "rippling",
        "recruiter_email",
        "recruiter_message",
        "screenshot",
        "html",
        "future",
    }


def test_application_strategy_matches_adr004_mapping():
    assert set(ApplicationStrategy) == {"auto", "ats", "manual", "unsupported"}


def test_ats_type_values():
    assert set(AtsType) == {
        "greenhouse",
        "lever",
        "ashby",
        "workday",
        "rippling",
        "generic",
        "none",
    }


def test_role_enum_values():
    assert set(Seniority) == {
        "junior",
        "mid",
        "senior",
        "lead",
        "manager",
        "executive",
        "unknown",
    }
    assert set(EmploymentType) == {
        "full_time",
        "part_time",
        "contract",
        "internship",
        "unknown",
    }
    assert set(WorkMode) == {"remote", "hybrid", "on_site", "unknown"}
    assert set(RoleFamily) == {"applied_ai", "forward_deployed", "fullstack", "other"}
    assert set(FitClass) == {"strong", "consider", "weak"}


def test_status_view_matches_adr012():
    assert set(OpportunityStatusView) == {
        "NEW",
        "REVIEW",
        "APPLYING",
        "SUBMITTED",
        "TRACKING",
        "CLOSED",
    }


def test_session_state_order_is_frozen_chain():
    # §7.5: BRIEF_READY → ANSWERS_REVIEWED → RESUME_SELECTED → FORM_FILLED
    #        → SUBMITTED | ABORTED (enum order encodes the transition chain).
    assert list(SessionState) == [
        SessionState.BRIEF_READY,
        SessionState.ANSWERS_REVIEWED,
        SessionState.RESUME_SELECTED,
        SessionState.FORM_FILLED,
        SessionState.SUBMITTED,
        SessionState.ABORTED,
    ]


def test_session_event_types_match_frozen_list():
    assert set(SessionEventType) == {
        "SESSION_CREATED",
        "ANSWERS_CONFIRMED",
        "RESUME_CHOSEN",
        "FORM_FILLING",
        "FORM_FILLED",
        "CHECKPOINT_PENDING",
        "HUMAN_SUBMIT",
        "SUBMITTED",
        "ABORTED",
        "OUTCOME_RECORDED",
    }


def test_answer_source_and_status_values():
    assert set(AnswerSource) == {"stored", "deterministic", "llm", "manual"}
    assert set(AnswerStatus) == {
        "auto",
        "confirm",
        "confirmed",
        "locked",
        "superseded",
    }


def test_provenance_and_event_namespace_values():
    assert set(Provenance) == {"parser", "provider", "llm", "human"}
    assert set(EventNamespace) == {"opp", "brief", "ans", "ses", "browser", "learn"}


def test_enums_are_strings():
    assert OpportunitySource.MANUAL_QUEUE == "manual_queue"
    assert SessionState.BRIEF_READY == "BRIEF_READY"
    assert AnswerStatus.LOCKED == "locked"


def test_package_version():
    assert __version__ == "5.1.0-rc1"


# ---------------------------------------------------------------------------
# Config loader (settings load with defaults).
# ---------------------------------------------------------------------------


def test_config_defaults_when_file_missing(monkeypatch):
    monkeypatch.setenv("COPILOT_CONFIG", "/nonexistent/copilot.yaml")
    cfg = load_copilot_config()
    assert cfg == CopilotConfig()
    assert cfg.db_path == "data/copilot.db"


def test_config_loads_yaml(tmp_path, monkeypatch):
    path = tmp_path / "copilot.yaml"
    path.write_text("copilot:\n  db_path: \"/tmp/test/copilot.db\"\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(path))
    assert load_copilot_config().db_path == "/tmp/test/copilot.db"


def test_config_ignores_unknown_keys(tmp_path, monkeypatch):
    # Forward-compatible: settings added later (e.g. CP-6-08) must not break
    # loaders that predate them.
    path = tmp_path / "copilot.yaml"
    path.write_text(
        "copilot:\n  db_path: \"/tmp/x.db\"\n  effort_cap_minutes: 40\n"
    )
    monkeypatch.setenv("COPILOT_CONFIG", str(path))
    assert load_copilot_config().db_path == "/tmp/x.db"


def test_config_missing_copilot_section_uses_defaults(tmp_path, monkeypatch):
    path = tmp_path / "copilot.yaml"
    path.write_text("other:\n  x: 1\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(path))
    assert load_copilot_config() == CopilotConfig()


def test_config_empty_file_uses_defaults(tmp_path, monkeypatch):
    path = tmp_path / "copilot.yaml"
    path.write_text("")
    monkeypatch.setenv("COPILOT_CONFIG", str(path))
    assert load_copilot_config() == CopilotConfig()


def test_config_malformed_raises(tmp_path, monkeypatch):
    path = tmp_path / "copilot.yaml"
    path.write_text("copilot: [not, a, mapping]\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(path))
    with pytest.raises(CopilotConfigurationError):
        load_copilot_config()


def test_config_unreadable_raises(tmp_path, monkeypatch):
    path = tmp_path / "copilot.yaml"
    path.write_text("copilot: {db_path: 'x'}\n")
    monkeypatch.setenv("COPILOT_CONFIG", str(path))
    path.chmod(0o000)
    with pytest.raises(CopilotConfigurationError):
        load_copilot_config()
    path.chmod(0o644)


def test_config_yaml_invalid_syntax_raises(tmp_path, monkeypatch):
    path = tmp_path / "copilot.yaml"
    path.write_text("copilot: {{{")
    monkeypatch.setenv("COPILOT_CONFIG", str(path))
    with pytest.raises(CopilotConfigurationError):
        load_copilot_config()


def test_yaml_dependency_available():
    # Loader depends on pyyaml (already in requirements.txt).
    assert hasattr(yaml, "safe_load")


# ---------------------------------------------------------------------------
# Exception hierarchy.
# ---------------------------------------------------------------------------


def test_exception_hierarchy():
    assert issubclass(CopilotConfigurationError, CopilotError)
    assert issubclass(CopilotError, Exception)
