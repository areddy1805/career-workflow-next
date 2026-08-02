"""Tests for CP-7-05: provider/ATS success + routing preference.

Seeds opportunities (via oppstore, distinct title/company for distinct
fingerprints) and learning outcomes; asserts counts, rates, medians,
best_strategy ties and preference ordering, plus empty-db safety.
"""

import pytest

from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.db.db import open_copilot_db
from src.copilot.learning.models import LearningOutcome
from src.copilot.learning.provider_success import (
    provider_success,
    routing_preference,
)
from src.copilot.learning.store import save_outcome
from src.copilot.oppstore import store as oppstore
from src.copilot.oppstore.model import CopilotOpportunity


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    cfg = tmp_path / "copilot.yaml"
    cfg.write_text(f'copilot:\n  db_path: "{tmp_path / "t" / "copilot.db"}"\n')
    monkeypatch.setenv("COPILOT_CONFIG", str(cfg))
    conn = open_copilot_db()
    yield conn
    conn.close()


def make_opp(title, company, **overrides) -> CopilotOpportunity:
    fields = dict(
        source=OpportunitySource.GENERIC_URL.value,
        title=title,
        company=company,
        provider_id="wellfound",
        ats_type="greenhouse",
        application_strategy=ApplicationStrategy.AUTO.value,
    )
    fields.update(overrides)
    return CopilotOpportunity(**fields)


def outcome(
    session_id, opportunity_id, *, outcome_value="applied", **overrides
) -> LearningOutcome:
    defaults = dict(
        session_id=session_id,
        opportunity_id=opportunity_id,
        provider_id="wellfound",
        ats_type="greenhouse",
        resume_profile="ai",
        outcome=outcome_value,
        timestamps={
            "submitted_at": "2026-01-02T00:00:00+00:00",
            "outcome_at": "2026-01-05T00:00:00+00:00",  # 3 days
        },
        created_at="2026-01-05T00:00:00+00:00",
    )
    defaults.update(overrides)
    return LearningOutcome(**defaults)


def day_outcome(session_id, opportunity_id, days, **overrides):
    """Outcome whose submitted_at→outcome_at gap is exactly ``days``."""
    return outcome(
        session_id,
        opportunity_id,
        timestamps={
            "submitted_at": f"2026-01-0{1}T00:00:00+00:00",
            "outcome_at": f"2026-01-0{1 + days}T00:00:00+00:00",
        },
        **overrides,
    )


# ------------------------------------------------------------ success


def test_provider_success_counts_and_rates(fresh_db):
    opp = make_opp("Senior Engineer", "Acme")
    oppstore.upsert(fresh_db, opp)
    for i, (outcome_value) in enumerate(
        ["applied", "applied", "interview", "rejected"]
    ):
        save_outcome(
            fresh_db,
            outcome(f"sess-{i}", opp.opportunity_id, outcome_value=outcome_value),
        )

    by_provider = provider_success(fresh_db)["by_provider"]
    bucket = by_provider["wellfound"]
    assert bucket["total"] == 4
    assert bucket["applied"] == 2
    assert bucket["interview"] == 1
    assert bucket["rejected"] == 1
    assert bucket["offer"] == 0
    assert bucket["archived"] == 0
    assert bucket["interview_rate"] == pytest.approx(0.5)
    assert bucket["offer_rate"] == pytest.approx(0.0)

    by_ats = provider_success(fresh_db)["by_ats_type"]
    assert by_ats["greenhouse"]["total"] == 4


def test_provider_success_rate_none_without_applied(fresh_db):
    opp = make_opp("Staff Engineer", "Beta")
    oppstore.upsert(fresh_db, opp)
    save_outcome(
        fresh_db,
        outcome("sess-1", opp.opportunity_id, outcome_value="interview"),
    )
    bucket = provider_success(fresh_db)["by_provider"]["wellfound"]
    assert bucket["interview_rate"] is None
    assert bucket["offer_rate"] is None


def test_median_days_to_response(fresh_db):
    opp = make_opp("Lead Engineer", "Gamma")
    oppstore.upsert(fresh_db, opp)
    # days: 1, 3, 5 → median 3; a row with missing timestamps is skipped
    for i, days in enumerate([1, 3, 5]):
        save_outcome(fresh_db, day_outcome(f"sess-{i}", opp.opportunity_id, days))
    save_outcome(
        fresh_db,
        outcome("sess-x", opp.opportunity_id, timestamps={}),
    )
    bucket = provider_success(fresh_db)["by_provider"]["wellfound"]
    assert bucket["median_days_to_response"] == pytest.approx(3)

    # even count: 1, 3, 5, 7 → 4.0
    save_outcome(fresh_db, day_outcome("sess-7", opp.opportunity_id, 7))
    bucket = provider_success(fresh_db)["by_provider"]["wellfound"]
    assert bucket["median_days_to_response"] == pytest.approx(4.0)


def test_median_none_when_all_timestamps_missing(fresh_db):
    opp = make_opp("Intern", "Delta")
    oppstore.upsert(fresh_db, opp)
    save_outcome(fresh_db, outcome("sess-1", opp.opportunity_id, timestamps={}))
    bucket = provider_success(fresh_db)["by_provider"]["wellfound"]
    assert bucket["median_days_to_response"] is None


def test_best_strategy_from_most_positive_opportunity(fresh_db):
    winner = make_opp(
        "Winner Role", "Winner Co", application_strategy=ApplicationStrategy.ATS.value
    )
    loser = make_opp(
        "Loser Role", "Loser Co", application_strategy=ApplicationStrategy.MANUAL.value
    )
    oppstore.upsert(fresh_db, winner)
    oppstore.upsert(fresh_db, loser)
    # winner: 2 interview; loser: 1 offer
    save_outcome(
        fresh_db, outcome("s1", winner.opportunity_id, outcome_value="interview")
    )
    save_outcome(
        fresh_db, outcome("s2", winner.opportunity_id, outcome_value="interview")
    )
    save_outcome(fresh_db, outcome("s3", loser.opportunity_id, outcome_value="offer"))

    bucket = provider_success(fresh_db)["by_provider"]["wellfound"]
    assert bucket["best_strategy"] == "ats"


def test_best_strategy_tie_first_alphabetically(fresh_db):
    ats_opp = make_opp(
        "A Role", "A Co", application_strategy=ApplicationStrategy.ATS.value
    )
    manual_opp = make_opp(
        "B Role", "B Co", application_strategy=ApplicationStrategy.MANUAL.value
    )
    oppstore.upsert(fresh_db, ats_opp)
    oppstore.upsert(fresh_db, manual_opp)
    save_outcome(
        fresh_db, outcome("s1", ats_opp.opportunity_id, outcome_value="interview")
    )
    save_outcome(
        fresh_db, outcome("s2", manual_opp.opportunity_id, outcome_value="offer")
    )

    bucket = provider_success(fresh_db)["by_provider"]["wellfound"]
    assert bucket["best_strategy"] == "ats"  # "ats" < "manual"


def test_best_strategy_none_without_opportunity(fresh_db):
    save_outcome(fresh_db, outcome("sess-1", None, outcome_value="interview"))
    bucket = provider_success(fresh_db)["by_provider"]["wellfound"]
    assert bucket["best_strategy"] is None


def test_provider_success_empty_db(fresh_db):
    assert provider_success(fresh_db) == {"by_provider": {}, "by_ats_type": {}}


# --------------------------------------------------------- preference


def test_routing_preference_ordering(fresh_db):
    good = make_opp("Good Role", "Good Co", provider_id="wellfound", ats_type="lever")
    mid = make_opp("Mid Role", "Mid Co", provider_id="wellfound", ats_type="greenhouse")
    oppstore.upsert(fresh_db, good)
    oppstore.upsert(fresh_db, mid)
    # lever: 1 offer / 1 applied → 1.0; greenhouse: 1 offer / 2 applied → 0.5
    save_outcome(
        fresh_db,
        outcome("s1", good.opportunity_id, outcome_value="offer", ats_type="lever"),
    )
    save_outcome(
        fresh_db,
        outcome("s1b", good.opportunity_id, outcome_value="applied", ats_type="lever"),
    )
    for i in range(2):
        save_outcome(
            fresh_db,
            outcome(
                f"s{2 + i}",
                mid.opportunity_id,
                outcome_value="offer" if i == 0 else "applied",
                ats_type="greenhouse",
            ),
        )
    save_outcome(
        fresh_db,
        outcome(
            "s4", mid.opportunity_id, outcome_value="applied", ats_type="greenhouse"
        ),
    )

    preference = routing_preference(fresh_db)["preference"]
    assert [item["ats_type"] for item in preference] == ["lever", "greenhouse"]
    assert preference[0]["score"] == pytest.approx(1.0)
    assert preference[1]["score"] == pytest.approx(0.5)


def test_routing_preference_tie_alphabetical(fresh_db):
    # two ats_types both with offer_rate 0.5 → alphabetical first wins
    for idx, (title, ats) in enumerate(
        [("Lever Role", "lever"), ("Greenhouse Role", "greenhouse")]
    ):
        opp = make_opp(title, f"Co {idx}", ats_type=ats)
        oppstore.upsert(fresh_db, opp)
        save_outcome(
            fresh_db,
            outcome(
                f"s{idx}a", opp.opportunity_id, outcome_value="offer", ats_type=ats
            ),
        )
        save_outcome(
            fresh_db,
            outcome(
                f"s{idx}b", opp.opportunity_id, outcome_value="applied", ats_type=ats
            ),
        )

    preference = routing_preference(fresh_db)["preference"]
    assert [item["ats_type"] for item in preference] == ["greenhouse", "lever"]


def test_routing_preference_excludes_no_applied(fresh_db):
    opp = make_opp("Only Interviews", "Co X", ats_type="ashby")
    oppstore.upsert(fresh_db, opp)
    save_outcome(
        fresh_db,
        outcome("s1", opp.opportunity_id, outcome_value="interview", ats_type="ashby"),
    )
    assert routing_preference(fresh_db)["preference"] == []


def test_routing_preference_empty_db(fresh_db):
    assert routing_preference(fresh_db) == {"preference": []}
