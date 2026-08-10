"""Phase F3 — resume routing from deterministic ranker family.

AI_FDE and AI_ENGINEERING route to the AI resume; pure FDE routes to the
customer-deployment resume; adjacent/generic fall back to the legacy
keyword router.
"""

from src.application.resume_router import ResumeRouter


def test_ai_fde_routes_to_ai_resume():
    r = ResumeRouter().route_from_family("AI_FDE", ai_depth=4)
    assert r["resume_type"] == "AI"
    assert "Applied_AI" in r["resume_path"]


def test_ai_engineering_routes_to_ai_resume():
    r = ResumeRouter().route_from_family("AI_ENGINEERING", ai_depth=3)
    assert r["resume_type"] == "AI"


def test_pure_fde_routes_to_fde_resume():
    r = ResumeRouter().route_from_family("FDE", ai_depth=2)
    assert r["resume_type"] == "FDE"
    assert "Forward_Deployed" in r["resume_path"]


def test_adjacent_falls_back_to_keyword_routing():
    r = ResumeRouter().route_from_family("AI_ADJACENT", ai_depth=2)
    assert r["resume_type"] in ("AI", "FDE")


def test_generic_falls_back_to_keyword_routing():
    r = ResumeRouter().route_from_family("GENERIC_ENGINEERING", ai_depth=0)
    assert r["resume_type"] in ("AI", "FDE")
