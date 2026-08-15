"""Phase F1 — application budget capacity simulation (offline).

Re-runs the production pipeline deterministically over the eval pool:
  normalize → gates (impossible/experience/desc-red-flag/title) →
  deterministic rank (new_ranker) → mode routing (naukri=AUTO,
  hiringcafe/jobspy=ATS|MANUAL) → quality threshold → company cap →
  budget 50/75/100/125/150/200 → select.

No LLM, no network, no production writes. Only reads:
  artifacts/evaluation/eval_pool.json
  artifacts/evaluation/ai_fde_eval_v1.json (excellent labels)
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from src.client.job_classifier import JobFilterPipeline2
from src.core.ranking.new_ranker import analyze as rank_analyze

ROOT = Path(__file__).resolve().parents[2]
POOL = ROOT / "artifacts/evaluation/eval_pool.json"
EVAL = ROOT / "artifacts/evaluation/ai_fde_eval_v1.json"

BUDGETS = [50, 75, 100, 125, 150, 200]
COMPANY_LIMIT = 2
MIN_SCORE = 20
AUTO_PROVIDERS = {"naukri"}
ATS_PROVIDERS = {"hiringcafe"}
MANUAL_PROVIDERS = {"jobspy"}


def load_pool():
    pool = json.loads(POOL.read_text(encoding="utf-8"))["pool"]
    # eval_pool has one row per job already (unique job_ids)
    return pool


def load_labels():
    eval_data = json.loads(EVAL.read_text(encoding="utf-8"))
    labels = {}
    for rec in eval_data["records"]:
        labels[rec["job_id"]] = {
            "bucket": rec["label_bucket"],
            "expected_family": rec["expected_role_family"],
        }
    return labels


def normalize_batch(classifier, jobs):
    """normalize_jobs needs a special attribute set; wrap each dict."""
    return classifier.normalize_jobs(jobs)


def run_gates(classifier, normalized):
    """Apply production hard gates in order. Returns survivors + gate stats."""
    stats = Counter()
    step = classifier.impossible_filter
    survivors = step(normalized)
    for j in normalized:
        if j not in survivors:
            stats["OBJECTIVELY_INCOMPATIBLE"] += 1

    step = classifier.experience_filter
    before = set(id(x) for x in survivors)
    survivors = step(survivors)
    stats["EXPERIENCE_*"] += len(before - set(id(x) for x in survivors))

    step = classifier.desc_red_flag_check
    before = set(id(x) for x in survivors)
    survivors = step(survivors)
    stats["DESC_RED_FLAG"] += len(before - set(id(x) for x in survivors))

    step = classifier.full_description_red_flag_check
    before = set(id(x) for x in survivors)
    survivors = step(survivors)
    stats["FULL_DESC_RED_FLAG"] += len(before - set(id(x) for x in survivors))

    step = classifier.title_filter
    before = set(id(x) for x in survivors)
    survivors = step(survivors)
    stats["NON_SOFTWARE_ROLE"] += len(before - set(id(x) for x in survivors))

    return survivors, stats


def score_and_rank(survivors):
    """Deterministic ranking: new_ranker final_score desc, age asc."""
    ranked = []
    for j in survivors:
        analysis = rank_analyze(
            {
                "title": j.get("title") or "",
                "company": j.get("company") or "",
                "description": j.get("description") or "",
                "tags": j.get("tags") or [],
                "experience": "",
                "location": j.get("location") or "",
            }
        )
        ranked.append(
            {
                "job": j,
                "analysis": analysis,
                "score": analysis["final_score"],
                "family": analysis["role_family"],
                "ai_depth": analysis["ai_depth"],
                "fde_band": analysis.get("fde_band", "NONE"),
                "age_days": j.get("days_old") or 0,
            }
        )
    ranked.sort(key=lambda r: (-r["score"], r["age_days"]))
    return ranked


def route_mode(job):
    """Mirror ApplicationResolutionService.resolve_from_job (no ATS detail
    fetching — hiringcafe apply URLs are ATS; jobspy = manual)."""
    pid = str(job.get("provider_id") or "unknown").lower()
    if pid in AUTO_PROVIDERS:
        if job.get("is_external_apply"):
            return "EXTERNAL"
        return "AUTO"
    if pid in ATS_PROVIDERS:
        return "ATS"
    if pid in MANUAL_PROVIDERS:
        return "MANUAL"
    return "EXTERNAL"


def simulate(ranked, budget):
    """Walk ranked pool in order. AUTO consumes budget; ATS/MANUAL/EXTERNAL
    route without budget. Constraints: quality >= MIN_SCORE, company cap."""
    company_counts: Counter = Counter()
    selected: list = []
    deferred_budget: list = []
    deferred_other: list = []
    routed: list = []
    budget_used = 0

    for r in ranked:
        job = r["job"]
        mode = route_mode(job)
        if mode == "AUTO":
            if r["score"] < MIN_SCORE:
                deferred_other.append(r)
                continue
            if company_counts[job.get("company") or ""] >= COMPANY_LIMIT:
                deferred_other.append(r)
                continue
            if budget_used >= budget:
                deferred_budget.append(r)
                continue
            budget_used += 1
            company_counts[job.get("company") or ""] += 1
            r["mode"] = "AUTO"
            selected.append(r)
        else:
            r["mode"] = mode
            routed.append(r)

    return {
        "budget": budget,
        "selected": selected,
        "routed": routed,
        "deferred_budget": deferred_budget,
        "deferred_other": deferred_other,
        "budget_used": budget_used,
        "company_counts": company_counts,
    }


def summarize(result, labels, label_job_ids):
    sel = result["selected"]
    fam = Counter(r["family"] for r in sel)
    depth = Counter(f"d{r['ai_depth']}" for r in sel)
    fde_band = Counter(r["fde_band"] for r in sel)
    companies = result["company_counts"]
    concentration = max(companies.values()) if companies else 0
    ai_fde = sum(fam.get(f, 0) for f in ("AI_ENGINEERING", "AI_FDE", "FDE"))
    total = len(sel) or 1

    # excellent labels captured
    exc_ai = sum(
        1
        for r in sel
        if r["job"].get("job_id") in labels
        and labels[r["job"].get("job_id")]["bucket"] == "excellent-ai"
    )
    exc_fde = sum(
        1
        for r in sel
        if r["job"].get("job_id") in labels
        and labels[r["job"].get("job_id")]["bucket"] == "excellent-fde"
    )

    # generic contamination in top-50 band
    contam50 = sum(1 for r in sel[:50] if r["family"] == "GENERIC_ENGINEERING")
    fp50 = sum(
        1
        for r in sel[:50]
        if r["job"].get("job_id") in labels
        and labels[r["job"].get("job_id")]["bucket"] == "false-positive-ai"
    )

    deferred_ai_fde = sum(
        1
        for r in result["deferred_budget"]
        if r["family"] in ("AI_ENGINEERING", "AI_FDE", "FDE")
    )

    # jobs lost solely to budget
    lost = len(result["deferred_budget"])

    return {
        "budget": result["budget"],
        "selected": total,
        "budget_used": result["budget_used"],
        "family": dict(fam),
        "ai_depth": dict(depth),
        "fde_band": dict(fde_band),
        "ai_fde_selected": ai_fde,
        "ai_fde_precision": round(ai_fde / total, 3),
        "excellent_ai_captured": exc_ai,
        "excellent_fde_captured": exc_fde,
        "generic_contamination_top50": contam50,
        "fp_ai_top50": fp50,
        "company_concentration_max": concentration,
        "deferred_ai_fde": deferred_ai_fde,
        "jobs_lost_to_budget": lost,
        "routed": len(result["routed"]),
    }


def main():
    pool = load_pool()
    labels = load_labels()
    print(f"Pool: {len(pool)} unique jobs")
    print(f"Labels: {len(labels)} (excellent-ai {sum(1 for v in labels.values() if v['bucket']=='excellent-ai')}, "
          f"excellent-fde {sum(1 for v in labels.values() if v['bucket']=='excellent-fde')})")
    print(f"Budgets: {BUDGETS}")

    classifier = JobFilterPipeline2()

    normalized = normalize_batch(classifier, pool)
    print(f"Normalized: {len(normalized)}")

    survivors, gate_stats = run_gates(classifier, normalized)
    print(f"Gate survivors: {len(survivors)}")
    print(f"Gate rejections: {dict(gate_stats)}")

    ranked = score_and_rank(survivors)
    print(f"Ranked: {len(ranked)}")

    rows = []
    for budget in BUDGETS:
        result = simulate(ranked, budget)
        rows.append(summarize(result, labels, None))
        s = rows[-1]
        print(
            f"B={s['budget']:>3} used={s['budget_used']:>3} sel={s['selected']:>3} "
            f"AI/FDE={s['ai_fde_selected']:>3} ({s['ai_fde_precision']:.2f}) "
            f"excAI={s['excellent_ai_captured']:>2} excFDE={s['excellent_fde_captured']:>2} "
            f"contam50={s['generic_contamination_top50']:>2} fp50={s['fp_ai_top50']:>2} "
            f"conc={s['company_concentration_max']:>2} defAI/FDE={s['deferred_ai_fde']:>3} "
            f"lost={s['jobs_lost_to_budget']:>3}"
        )

    out = ROOT / "artifacts/evaluation/budget_simulation.json"
    out.write_text(
        json.dumps(
            {
                "source_pool": str(POOL),
                "pool_size": len(pool),
                "gate_survivors": len(survivors),
                "gate_rejections": dict(gate_stats),
                "budgets": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
