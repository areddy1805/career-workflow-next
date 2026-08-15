"""Ranker evaluation harness for ai_fde_eval_v1 (Phase B, deterministic, no LLM).

Usage:
  python tools/evaluation/eval_harness.py                # baseline (current ranker)
  python tools/evaluation/eval_harness.py --ranker new   # pluggable NEW_RANKER

A ranker is any callable `score(job: dict) -> float` where `job` is a record
from ai_fde_eval_v1.json. CURRENT_RANKER uses the observed `current_rank`
(reverse order; unranked = +inf). NEW_RANKER is a stub importing
`src.core.ranking.new_ranker.score` if present, else a placeholder — Phase C/D
implements the real one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "artifacts" / "evaluation" / "ai_fde_eval_v1.json"

TARGET_FAMILIES = {"AI_ENGINEERING", "FDE", "AI_FDE"}


def load_eval() -> list[dict]:
    return json.loads(EVAL.read_text())["records"]


def current_ranker(jobs: list[dict]) -> list[dict]:
    def key(j: dict) -> tuple:
        r = j.get("current_rank")
        return (float("inf") if r is None else r, j["job_id"])

    return sorted(jobs, key=key)


def default_new_ranker(jobs: list[dict]) -> list[dict]:
    """Placeholder: same ordering as current. Phase C/D replaces this."""
    return current_ranker(jobs)


def _load_new_ranker(jobs: list[dict]) -> list[dict]:
    try:
        from src.core.ranking.new_ranker import score  # type: ignore

        return sorted(jobs, key=lambda j: -score(j))
    except ImportError:
        return default_new_ranker(jobs)


def target(j: dict) -> bool:
    return j["expected_role_family"] in TARGET_FAMILIES


def metrics(ranked: list[dict]) -> dict:
    n = len(ranked)
    t20 = ranked[:20]
    t50 = ranked[:50]

    def pct(rs, pred) -> float:
        if not rs:
            return 0.0
        return sum(1 for r in rs if pred(r)) / min(len(rs), 50)

    return {
        "n": n,
        "ai_p@20": pct(t20, lambda r: r["expected_role_family"] == "AI_ENGINEERING"),
        "ai_p@50": pct(t50, lambda r: r["expected_role_family"] == "AI_ENGINEERING"),
        "fde_p@20": pct(t20, lambda r: r["expected_role_family"] in ("FDE", "AI_FDE")),
        "fde_p@50": pct(t50, lambda r: r["expected_role_family"] in ("FDE", "AI_FDE")),
        "ai_fde_p@50": pct(t50, target),
        "generic_contamination@50": sum(
            1 for r in t50 if r["expected_role_family"] == "GENERIC_ENGINEERING"
        ),
        "fp_ai@50": sum(1 for r in t50 if r["expected_role_family"] == "FALSE_POSITIVE"),
        "excellent_recall@50": sum(1 for r in t50 if r["label_bucket"] == "excellent-ai")
        / max(1, sum(1 for r in ranked if r["label_bucket"] == "excellent-ai")),
        "targets_trapped_below_50": sum(
            1
            for r in ranked
            if target(r) and (r["current_rank"] is None or r["current_rank"] > 50)
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranker", choices=["current", "new"], default="current")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    jobs = load_eval()
    ranked = _load_new_ranker(jobs) if args.ranker == "new" else current_ranker(jobs)
    m = metrics(ranked)

    if args.json:
        print(json.dumps({"ranker": args.ranker, **m}, indent=1))
        return

    print(f"=== {args.ranker.upper()} RANKER — eval metrics (n={m['n']}) ===")
    for k in ("ai_p@20", "ai_p@50", "fde_p@20", "fde_p@50", "ai_fde_p@50",
              "generic_contamination@50", "fp_ai@50", "excellent_recall@50",
              "targets_trapped_below_50"):
        print(f"  {k}: {m[k]}")


if __name__ == "__main__":
    main()
