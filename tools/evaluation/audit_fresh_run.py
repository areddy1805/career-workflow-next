"""Phase F6 — fresh-run validation audit (offline, deterministic).

Re-runs the deterministic ranker over a fresh production run's acquired
pool and emits a compact audit table (rank, title, company, provider,
role_family, ai_depth, fde_band, score, profile, status) plus the F7
quality-gate checks.

Sources (read-only):
  artifacts/runs/<run_id>/job_trace.json   — every acquired job (title/company)
  artifacts/runs/<run_id>/selected_jobs.json — top picks w/ deterministic_rank
  data/job_search_cache.json              — descriptions by job_id (fresh pool)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    return d.get("data", d) if isinstance(d, dict) and "data" in d else d


def main(run_id: str):
    run_dir = ROOT / "artifacts" / "runs" / run_id
    trace = load_json(run_dir / "job_trace.json")
    raw_cache = json.loads((ROOT / "data" / "job_search_cache.json").read_text(encoding="utf-8"))
    cache = [e.get("job") or {} for e in raw_cache.get("jobs") or []]
    cache_by_id = {str(j.get("job_id")): j for j in cache}

    from src.core.ranking.new_ranker import analyze
    from src.client.job_classifier import JobFilterPipeline2

    classifier = JobFilterPipeline2()
    raw_jobs = []
    seen = set()
    for pid, v in trace.items():
        title = v.get("title", "")
        company = v.get("company", "")
        jid = None
        for ev in v.get("timeline", []):
            det = ev.get("details") or {}
            if det.get("provider_job_id"):
                jid = str(det["provider_job_id"])
                break
        key = (title, company)
        if key in seen:
            continue
        seen.add(key)
        cached = cache_by_id.get(jid) if jid else None
        raw_jobs.append(
            {
                "job_id": jid,
                "title": title,
                "company": company,
                "location": (cached or {}).get("location") or "",
                "description": (cached or {}).get("description") or "",
                "tags": (cached or {}).get("tags") or [],
                "provider_id": str(v.get("provider_id") or (cached or {}).get("provider_id") or "?"),
                "posted_date": "",
                "experience": (cached or {}).get("experience") or "",
            }
        )

    normalized = classifier.normalize_jobs(raw_jobs)
    # Production hard gates (mirrors run selection path)
    gated = classifier.impossible_filter(normalized)
    gated = classifier.experience_filter(gated)
    gated = classifier.desc_red_flag_check(gated)
    gated = classifier.title_filter(gated)

    rows = []
    for j in gated:
        analysis = analyze(
            {
                "title": j.get("title"),
                "company": j.get("company"),
                "description": j.get("description"),
                "tags": j.get("tags") or [],
                "experience": "",
                "location": j.get("location"),
            }
        )
        rows.append(
            {
                "title": j.get("title"),
                "company": j.get("company"),
                "provider": str(j.get("provider_id") or "?"),
                "job_id": j.get("job_id"),
                "family": analysis["role_family"],
                "depth": analysis["ai_depth"],
                "fde_band": analysis.get("fde_band", "NONE"),
                "score": analysis["final_score"],
                "has_desc": bool((j.get("description") or "").strip()),
            }
        )

    rows.sort(key=lambda r: (-r["score"], r["title"]))
    print(f"Pool (deduped by title/company): {len(rows)}")
    print(f"With description: {sum(1 for r in rows if r['has_desc'])}")
    print()
    fam = Counter(r["family"] for r in rows)
    print("=== ROLE FAMILY (whole fresh pool) ===")
    for f, c in fam.most_common():
        print(f"  {f:<22}{c}")
    print()

    # Ranked composition of top N by deterministic score
    for n in (20, 50, 100):
        top = rows[:n]
        f = Counter(r["family"] for r in top)
        ai_fde = sum(f.get(k, 0) for k in ("AI_ENGINEERING", "AI_FDE", "FDE"))
        print(
            f"TOP {n}: AI/FDE={ai_fde} ({ai_fde / n:.0%})  "
            f"GENERIC={f.get('GENERIC_ENGINEERING', 0)}  "
            f"AI_ADJACENT={f.get('AI_ADJACENT', 0)}  "
            f"NON_TARGET={f.get('NON_TARGET', 0)}"
        )
    print()

    # Ranked top 20 detail
    print("=== TOP 20 (deterministic ranker, fresh pool) ===")
    for i, r in enumerate(rows[:20], 1):
        print(
            f"{i:>3} {r['score']:6.2f} {r['family']:<18} d{r['depth']} "
            f"{r['fde_band']:<9} {r['title'][:40]:<40} @ {r['company'][:20]}"
        )
    print()

    # F7 checks
    print("=== F7 QUALITY GATES ===")
    # 1: excellent-AI not trapped below generic
    ai_top = [r for r in rows if r["family"] in ("AI_ENGINEERING", "AI_FDE")]
    gen_ranks = [i for i, r in enumerate(rows) if r["family"] == "GENERIC_ENGINEERING"]
    worst_ai = max((i for i, r in enumerate(rows) if r["family"] in ("AI_ENGINEERING", "AI_FDE")), default=None)
    first_gen = min(gen_ranks, default=None)
    print(f"1. highest-ranked GENERIC at rank {first_gen + 1 if first_gen is not None else 'N/A'}; "
          f"AI/FDE count above it: {first_gen if first_gen is not None else 'N/A'}")
    # 2: FDE not trapped below generic
    fde_ranks = [i for i, r in enumerate(rows) if r["family"] == "FDE"]
    print(f"2. FDE jobs: {len(fde_ranks)} — ranks: {[i + 1 for i in fde_ranks[:10]]}")
    # 3: generic doesn't dominate top 50
    print(f"3. generic in top 50: {sum(1 for r in rows[:50] if r['family']=='GENERIC_ENGINEERING')}")
    # 4: RPA/QA/ERP/support not AI from keywords
    noise = [r for r in rows if any(k in r["title"].lower() for k in ("rpa", "qa", "test", "erp", "support"))]
    noise_ai = [r for r in noise if r["family"] in ("AI_ENGINEERING", "AI_FDE")]
    print(f"4. noise titles (rpa/qa/test/erp/support) = {len(noise)}, of which AI family = {len(noise_ai)}")
    # 8: provider coverage
    print(f"8. provider mix (pool): {dict(Counter(r['provider'] for r in rows).most_common(6))}")


if __name__ == "__main__":
    main(sys.argv[1])
