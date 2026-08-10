"""Build the deterministic evaluation pool from a live run + acquisition cache.

Phase B (measurement only). Reads run artifacts from artifacts/runs/<run_id>/ and
data/job_search_cache.json, and emits:

  artifacts/evaluation/eval_pool.json      — every job with status/score/rank/description
  artifacts/evaluation/eval_pool_compact.tsv — compact rows for manual labeling

No production code is touched. The pool is the ONLY input to the labeling
process and the baseline metrics.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "artifacts" / "runs"
CACHE = ROOT / "data" / "job_search_cache.json"
OUT_DIR = ROOT / "artifacts" / "evaluation"

# job_id -> status info, populated from the run artifacts
_STATUS_FILES = {
    "SELECTED": "selected_jobs.json",
    "DEFERRED": "deferred_jobs.json",
    "REJECTED": "rejected_jobs.json",
    "ROUTED_MANUAL": "manual_review.json",
    "ROUTED_ATS": "ats_queue.json",
}


def load_run(run_id: str) -> dict:
    run_dir = RUNS / run_id
    if not run_dir.exists():
        raise SystemExit(f"run dir not found: {run_dir}")
    jobs: dict[str, dict] = {}
    order: list[str] = []

    # 1) selected jobs: richest records, score + search metadata, order = rank
    sel_path = run_dir / "selected_jobs.json"
    if sel_path.exists():
        for i, rec in enumerate(json.loads(sel_path.read_text())["data"], start=1):
            jid = rec["job_id"]
            rec = dict(rec)
            rec["_status"] = "SELECTED"
            rec["_rank"] = i
            jobs[jid] = rec
            order.append(jid)

    # 2) shallow status files
    for status, fname in _STATUS_FILES.items():
        path = run_dir / fname
        if not path.exists():
            continue
        for rec in json.loads(path.read_text())["data"]:
            jid = rec["job_id"]
            base = jobs.get(jid, {})
            base["job_id"] = jid
            base["title"] = rec.get("title")
            base["company"] = rec.get("company")
            base["provider_id"] = rec.get("provider_id")
            base["_status"] = status
            base["_reason"] = rec.get("reason_code", "")
            base["_explanation"] = rec.get("explanation", "")
            if "_rank" not in base:
                base["_rank"] = None
            jobs[jid] = base
            if jid not in order:
                order.append(jid)

    # 3) routed rank from explanation "rank #N"
    rank_re = re.compile(r"rank #(\d+)")
    for jid in jobs:
        m = rank_re.search(jobs[jid].get("_explanation", ""))
        if m:
            jobs[jid]["_rank"] = int(m.group(1))

    return {"run_id": run_id, "jobs": jobs, "order": order}


def merge_cache(jobs: dict[str, dict]) -> dict[str, dict]:
    """Attach description/experience/tags from the acquisition cache by job_id."""
    if not CACHE.exists():
        print("warning: no job_search_cache.json, descriptions will be sparse")
        return jobs
    cache = json.loads(CACHE.read_text())["jobs"]
    for entry in cache:
        job = entry.get("job") or {}
        jid = job.get("job_id")
        if not jid or jid not in jobs:
            continue
        rec = jobs[jid]
        for key in ("description", "experience", "salary", "location", "tags", "apply_url"):
            if key not in rec or rec.get(key) in (None, ""):
                rec[key] = job.get(key)
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="20260810T004012474615Z")
    args = ap.parse_args()

    run = load_run(args.run)
    jobs = merge_cache(run["jobs"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pool = []
    for jid in run["order"]:
        rec = jobs[jid]
        pool.append(
            {
                "job_id": jid,
                "title": rec.get("title"),
                "company": rec.get("company"),
                "location": rec.get("location"),
                "experience": rec.get("experience"),
                "status": rec.get("_status"),
                "reason": rec.get("_reason"),
                "explanation": rec.get("_explanation"),
                "rank": rec.get("_rank"),
                "score": rec.get("score"),
                "ai_score": rec.get("ai_score"),
                "subtrack": rec.get("subtrack"),
                "priority": rec.get("priority"),
                "search_profile": rec.get("search_profile"),
                "search_query": rec.get("search_query"),
                "provider_id": rec.get("provider_id"),
                "tags": rec.get("tags"),
                "description": rec.get("description"),
            }
        )

    (OUT_DIR / "eval_pool.json").write_text(
        json.dumps({"run_id": args.run, "pool": pool}, indent=1)
    )

    with (OUT_DIR / "eval_pool_compact.tsv").open("w") as fh:
        fh.write("job_id\tstatus\trank\tscore\ttitle\tcompany\texp\tprovider\tdesc\n")
        for p in pool:
            desc = (p["description"] or "").replace("\t", " ").replace("\n", " ")
            desc = desc[:320]
            title = (p["title"] or "").replace("\t", " ")
            company = (p["company"] or "?").replace("\t", " ")
            fh.write(
                f"{p['job_id']}\t{p['status']}\t{p['rank'] or ''}\t{p['score'] or ''}\t"
                f"{title}\t{company}\t{p['experience'] or ''}\t{p['provider_id'] or ''}\t{desc}\n"
            )

    n = len(pool)
    from collections import Counter

    print(f"pool: {n} jobs")
    print(Counter(p["status"] for p in pool))
    print(f"with description: {sum(1 for p in pool if p['description'])}")
    print(f"wrote {OUT_DIR / 'eval_pool.json'} and eval_pool_compact.tsv")


if __name__ == "__main__":
    main()
