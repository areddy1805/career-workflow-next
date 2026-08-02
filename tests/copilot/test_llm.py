"""Unit tests for CP-2-06: gated LLM prose augmentation (mocked LLM)."""

from src.copilot.brief.assembler import assemble_brief
from src.copilot.brief.llm import BRIEF_LLM_ENABLED, prose_summary
from src.copilot.constants import OpportunitySource
from src.copilot.oppstore.model import CopilotOpportunity


def make_opportunity(**overrides) -> CopilotOpportunity:
    defaults = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title="Staff Engineer",
        company="Acme Corp",
        description_text="Acme builds the data platform for retail analytics.",
    )
    defaults.update(overrides)
    return CopilotOpportunity(**defaults)


def test_flag_off_by_default():
    assert BRIEF_LLM_ENABLED is False


def test_disabled_returns_none_and_no_call():
    calls = []

    def llm_call(prompt):
        calls.append(prompt)
        return "summary"

    assert prose_summary(make_opportunity(), llm_call=llm_call) is None
    assert calls == []


def test_enabled_calls_llm_once_and_caches():
    calls = []

    def llm_call(prompt):
        calls.append(prompt)
        return "A concise summary."

    opp = make_opportunity()
    cache: dict[str, str] = {}
    summary = prose_summary(opp, llm_call=llm_call, enabled=True, cache=cache)
    assert summary == "A concise summary."
    # cache hit → no second call
    again = prose_summary(opp, llm_call=llm_call, enabled=True, cache=cache)
    assert again == summary
    assert len(calls) == 1


def test_no_provider_returns_none():
    assert prose_summary(make_opportunity(), enabled=True) is None


def test_empty_llm_result_returns_none():
    opp = make_opportunity()
    cache: dict[str, str] = {}
    assert (
        prose_summary(opp, llm_call=lambda prompt: "", enabled=True, cache=cache)
        is None
    )
    assert cache == {}


def test_input_truncated_to_budget():
    seen = []

    def llm_call(prompt):
        seen.append(prompt)
        return "ok"

    long_text = "x" * 9000
    opp = make_opportunity(description_text=long_text)
    prose_summary(opp, llm_call=llm_call, enabled=True, max_input_chars=100)
    # prompt = "Summarize this job posting in 3 sentences: " + 100 chars
    assert seen[0].endswith("x" * 100)


def test_output_capped():
    opp = make_opportunity()
    summary = prose_summary(
        opp, llm_call=lambda prompt: "y" * 2000, enabled=True,
        max_output_chars=50,
    )
    assert len(summary) == 50


# ----------------------------------------------------- brief wiring


def test_brief_prose_summary_section_llm_source():
    opp = make_opportunity()
    summary = prose_summary(
        opp, llm_call=lambda prompt: "A short summary.", enabled=True
    )
    brief = assemble_brief(opp, prose_summary=summary)
    assert brief.prose_summary == "A short summary."
    assert brief.section_sources["prose_summary"] == "llm"
    assert brief.to_dict()["prose_summary"] == "A short summary."


def test_brief_without_prose_summary():
    brief = assemble_brief(make_opportunity())
    assert brief.prose_summary is None
    assert "prose_summary" not in brief.section_sources
