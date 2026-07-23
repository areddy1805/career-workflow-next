from __future__ import annotations

import pytest
from src.acquisition.providers.jobspy_planner import (
    GoogleStrategy,
    IndeedStrategy,
    LinkedInStrategy,
    JobSpySearchPlanner,
)


def test_google_strategy_quoting_and_negatives():
    strat = GoogleStrategy()

    # Single word, no negatives
    assert strat.format_query("Python", []) == "Python"

    # Multi word keyword, no negatives -> should quote
    assert strat.format_query("AI Engineer", []) == '"AI Engineer"'

    # Already quoted multi word -> should not double quote
    assert strat.format_query('"AI Engineer"', []) == '"AI Engineer"'

    # Single word, single negative
    assert strat.format_query("Python", ["SAP"]) == "Python -SAP"

    # Multi word with multi word negatives
    assert (
        strat.format_query("AI Engineer", ["SAP", "Sales Force"])
        == '"AI Engineer" -SAP -"Sales Force"'
    )


def test_indeed_strategy_quoting_and_negatives():
    strat = IndeedStrategy()
    assert strat.format_query("Python", []) == "Python"
    assert strat.format_query("AI Engineer", []) == '"AI Engineer"'
    assert strat.format_query("AI Engineer", ["SAP"]) == '"AI Engineer" -SAP'


def test_linkedin_strategy_quotes_but_ignores_negatives():
    strat = LinkedInStrategy()
    assert strat.format_query("Python", ["SAP"]) == "Python"
    assert strat.format_query("AI Engineer", ["SAP"]) == '"AI Engineer"'
