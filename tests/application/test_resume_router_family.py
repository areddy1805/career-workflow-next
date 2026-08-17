"""Phase F3 — resume routing from deterministic ranker family.

AI_FDE and AI_ENGINEERING route to the AI resume; pure FDE routes to the
customer-deployment resume; adjacent/generic fall back to the legacy
keyword router.

Registry-integrity note (2026-08-17, CP-0-03): the historical registry
referenced docs/resume/Applied_AI.pdf and docs/resume/Forward_Deployed.pdf,
neither of which ever existed on disk. The authoritative artifact is
docs/resume/Abhilash_Reddy_ResumeU.pdf (the only real resume). Tests assert
that routed paths resolve to existing files — a stronger contract that
catches a broken registry, which the old filename-string assertions could not.
"""

from pathlib import Path

from src.application.resume_router import ResumeRouter


def _assert_real_file(resume_path: str) -> None:
    assert resume_path, "resume_path must not be empty"
    assert Path(resume_path).is_file(), (
        f"routed resume must exist on disk; got {resume_path!r}"
    )


def test_ai_fde_routes_to_ai_resume():
    r = ResumeRouter().route_from_family("AI_FDE", ai_depth=4)
    assert r["resume_type"] == "AI"
    # Real registry contract: routed resume exists (regression: old registry
    # pointed at nonexistent Applied_AI.pdf).
    _assert_real_file(r["resume_path"])


def test_ai_engineering_routes_to_ai_resume():
    r = ResumeRouter().route_from_family("AI_ENGINEERING", ai_depth=3)
    assert r["resume_type"] == "AI"
    _assert_real_file(r["resume_path"])


def test_pure_fde_routes_to_fde_resume():
    r = ResumeRouter().route_from_family("FDE", ai_depth=2)
    assert r["resume_type"] == "FDE"
    _assert_real_file(r["resume_path"])


def test_adjacent_falls_back_to_keyword_routing():
    r = ResumeRouter().route_from_family("AI_ADJACENT", ai_depth=2)
    assert r["resume_type"] in ("AI", "FDE")
    _assert_real_file(r["resume_path"])


def test_generic_falls_back_to_keyword_routing():
    r = ResumeRouter().route_from_family("GENERIC_ENGINEERING", ai_depth=0)
    assert r["resume_type"] in ("AI", "FDE")
    _assert_real_file(r["resume_path"])
