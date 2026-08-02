"""Unit tests for CP-2-05: likely questions service."""

from src.copilot.brief.assembler import assemble_brief
from src.copilot.brief.questions import CorpusQuestion, likely_questions
from src.copilot.constants import OpportunitySource
from src.copilot.oppstore.model import CopilotOpportunity


def make_opportunity(**overrides) -> CopilotOpportunity:
    defaults = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title="Staff Engineer",
        company="Acme Corp",
        description_text=(
            "You will own prioritization across the platform team and "
            "improve the onboarding workflow."
        ),
    )
    defaults.update(overrides)
    return CopilotOpportunity(**defaults)


# -------------------------------------------------------- corpus scoring


def test_ats_specific_question_selected_for_matching_ats():
    opp = make_opportunity(ats_type="greenhouse")
    questions = likely_questions(opp)
    texts = [q.question for q in questions]
    assert "improve our interview process" in " ".join(texts)


def test_ats_specific_question_excluded_for_other_ats():
    opp = make_opportunity(ats_type="lever")
    questions = likely_questions(opp)
    assert not any(
        "improve our interview process" in q.question for q in questions
    )


def test_keyword_boost_ranks_above_generic():
    opp = make_opportunity(ats_type="lever")
    questions = likely_questions(opp, limit=10)
    # "What is your approach to prioritization?" matches the description's
    # "prioritization" keyword → must outrank the non-boosted generic ones
    assert questions[0].question.startswith("What is your approach")
    assert questions[0].answer


def test_limit_respected():
    opp = make_opportunity(ats_type="greenhouse")
    assert len(likely_questions(opp, limit=2)) == 2


def test_zero_score_questions_excluded():
    corpus = [
        CorpusQuestion("Irrelevant ATS question", "n/a", ats_types=("workday",)),
    ]
    opp = make_opportunity(ats_type="lever")
    assert likely_questions(opp, corpus=corpus) == []


def test_generic_questions_apply_to_any_ats():
    opp = make_opportunity(ats_type="rippling")
    questions = likely_questions(opp)
    assert any(
        "project you led end to end" in q.question for q in questions
    )


def test_empty_corpus_returns_empty():
    opp = make_opportunity()
    assert likely_questions(opp, corpus=[]) == []


def test_no_description_still_returns_ats_matches():
    opp = make_opportunity(ats_type="greenhouse", description_text=None)
    questions = likely_questions(opp)
    assert any(
        "improve our interview process" in q.question for q in questions
    )


# -------------------------------------------------------- brief wiring


def test_brief_questions_section():
    opp = make_opportunity(ats_type="greenhouse")
    questions = likely_questions(opp)
    brief = assemble_brief(opp, questions=questions)
    assert brief.questions is questions
    assert brief.section_sources["questions"] == "deterministic"
    data = brief.to_dict()
    assert data["questions"][0]["question"]
    assert data["questions"][0]["answer"]


def test_brief_without_questions():
    brief = assemble_brief(make_opportunity())
    assert brief.questions is None
    assert "questions" not in brief.section_sources
