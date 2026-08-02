"""Likely questions service (CP-2-05).

Scores a question corpus by ATS-type match + description-keyword overlap and
returns top-N questions with pre-resolved answers (05 §2 #8). The corpus is
injectable — the Answer Bank (CP-3-02) is the production source; a small
built-in starter corpus keeps the brief deterministic-first until then.
"""

import re
from dataclasses import dataclass

from src.copilot.brief.models import LikelyQuestion
from src.copilot.oppstore.model import CopilotOpportunity


@dataclass(frozen=True)
class CorpusQuestion:
    """One corpus entry: question, pre-resolved answer, ATS applicability."""

    question: str
    answer: str
    ats_types: tuple[str, ...] = ()  # empty = applies to any ATS
    keywords: tuple[str, ...] = ()  # description match terms (boost)


_DEFAULT_CORPUS: tuple[CorpusQuestion, ...] = (
    CorpusQuestion(
        "Tell me about a project you led end to end.",
        "Answer with the STAR method in 2-3 minutes; lead with impact metrics.",
    ),
    CorpusQuestion(
        "Why do you want to work here?",
        "Connect the company mission to your trajectory; name one concrete "
        "product signal.",
    ),
    CorpusQuestion(
        "Describe a time you dealt with ambiguity.",
        "STAR; show your process (stakeholders, options, decision), not just "
        "the outcome.",
    ),
    CorpusQuestion(
        "How would you improve our interview process?",
        "Greenhouse-style culture question; be candid and specific.",
        ats_types=("greenhouse",),
    ),
    CorpusQuestion(
        "What is your approach to prioritization?",
        "Lever-style: name a framework (RICE/Eisenhower) and a recent trade-off.",
        ats_types=("lever",),
        keywords=("prioritization", "priority"),
    ),
    CorpusQuestion(
        "Walk us through a complex workflow you own.",
        "Workday-style systems question; draw the end-to-end flow with owners.",
        ats_types=("workday",),
        keywords=("workflow", "process"),
    ),
)


def _keyword_hits(question: CorpusQuestion, description: str | None) -> int:
    if not description:
        return 0
    low = description.lower()
    return sum(
        1
        for keyword in question.keywords
        if re.search(rf"\b{re.escape(keyword.lower())}\b", low)
    )


def _score(
    question: CorpusQuestion, ats_type: str | None, description: str | None
) -> float:
    score = 0.0
    if not question.ats_types or ats_type in question.ats_types:
        score += 1.0
    score += 0.5 * _keyword_hits(question, description)
    return score


def likely_questions(
    opportunity: CopilotOpportunity,
    *,
    corpus: list[CorpusQuestion] | None = None,
    limit: int = 5,
) -> list[LikelyQuestion]:
    """Top-N likely screening questions with pre-resolved answers.

    Ranking: ATS-applicable questions score 1.0, plus 0.5 per description
    keyword hit; zero-scoring questions are excluded; ties keep corpus order.
    ``corpus`` defaults to the built-in starter corpus; the Answer Bank
    (CP-3-02) supplies the production corpus.
    """
    entries = list(corpus) if corpus is not None else list(_DEFAULT_CORPUS)
    description = opportunity.description_text
    ats_type = opportunity.ats_type
    scored = [
        (question, _score(question, ats_type, description))
        for question in entries
    ]
    ranked = [q for q, score in scored if score > 0]
    ranked.sort(key=lambda q: _score(q, ats_type, description), reverse=True)
    return [
        LikelyQuestion(question=q.question, answer=q.answer)
        for q in ranked[:limit]
    ]
