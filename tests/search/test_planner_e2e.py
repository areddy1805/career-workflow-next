"""Tests for SearchPlanner query generation (Phase E fixes).

Covers: per-profile locations, title-cap semantics (locations must not trade
off title coverage), and JobSpy budget enforcement.
"""

from src.search.planner import SearchPlanner
from src.acquisition.providers.jobspy_planner import JobSpySearchPlanner


class _FakePlanner(SearchPlanner):
    def __init__(self, profiles, user_profile, planner_config):
        self.config_dir = None
        self.user_profile = user_profile
        self.planner_config = planner_config
        self.search_profiles = profiles
        self.technology_profiles = {}
        self.company_profiles = {}
        self.negative_profiles = {}


def test_per_profile_locations_win_over_global():
    p = _FakePlanner(
        {"ai": {"titles": ["AI Engineer", "LLM Engineer"], "locations": ["Remote", "Pune"]}},
        {"active_profiles": ["ai"], "preferred_locations": ["Mumbai"]},
        {"max_queries_per_profile": 50},
    )
    qs = p.generate_queries()
    locs = {q["location"] for q in qs}
    assert locs == {"Remote", "Pune"}
    assert len(qs) == 4  # 2 titles x 2 locations


def test_cap_limits_titles_not_locations():
    # 3 titles, 2 locations, cap 2 -> 2 titles x 2 locations = 4 queries,
    # never 2 queries total (the pre-Phase-E flatten bug).
    p = _FakePlanner(
        {"ai": {"titles": ["A1", "A2", "A3"], "locations": ["L1", "L2"]}},
        {"active_profiles": ["ai"], "preferred_locations": ["X"]},
        {"max_queries_per_profile": 2},
    )
    qs = p.generate_queries()
    assert len(qs) == 4
    assert {q["location"] for q in qs} == {"L1", "L2"}


def test_real_config_coverage():
    p = SearchPlanner()
    qs = p.generate_queries()
    assert len(qs) > 100
    profiles = {q["search_profile"] for q in qs}
    assert {"ai", "fde"} <= profiles
    locs = {q["location"] for q in qs}
    assert {"Pune", "Remote", "Bengaluru"} <= locs


def test_jobspy_budget_per_profile():
    profiles = {
        "p1": {
            "priority": 100,
            "providers": ["google"],
            "max_queries": 4,
            "layers": {"roles": ["AI Engineer", "LLM Engineer", "RAG Engineer", "ML Engineer", "GenAI Engineer"]},
        },
        "p2": {
            "priority": 50,
            "providers": ["google"],
            "max_queries": 2,
            "layers": {"roles": ["Applied AI", "Forward Deployed Engineer", "Implementation Engineer"]},
        },
    }
    pl = JobSpySearchPlanner(profiles)
    qs = pl.generate_planned_searches(["Pune"])
    from collections import Counter
    by_profile = Counter(q.search_profile for q in qs)
    assert by_profile == {"p1": 4, "p2": 2}


def test_jobspy_frameworks_capped():
    profiles = {
        "p1": {
            "priority": 100,
            "providers": ["google"],
            "max_queries": 100,
            "max_titles": 1,
            "max_frameworks": 2,
            "layers": {
                "roles": ["AI Engineer", "LLM Engineer"],
                "frameworks": ["LangChain", "LangGraph", "OpenAI", "Anthropic"],
            },
        },
    }
    pl = JobSpySearchPlanner(profiles)
    qs = pl.generate_planned_searches(["Pune"])
    # 1 role + 2 frameworks = 3 terms
    assert len(qs) == 3


def test_linkedin_negatives_still_ignored():
    from src.acquisition.providers.jobspy_planner import LinkedInStrategy
    assert LinkedInStrategy().format_query("AI Engineer", ["SAP"]) == '"AI Engineer"'
