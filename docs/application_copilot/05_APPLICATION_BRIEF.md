# Application Brief

**Version:** 1.0.0
**Status:** Approved (ADR-013)

---

## 1. Purpose

Before the user opens the apply flow, CareerFlow produces an **intelligence briefing** for the opportunity. The Brief is the product: it converts the decision *should I apply / how should I apply* from guesswork into evidence. It is **deterministic-first**, LLM-augmented only where needed, cached, and always explainable.

## 2. Contents (frozen sections)

| # | Section | Source (deterministic unless noted) |
|---|---|---|
| 1 | **Verdict** | Apply / Consider / Skip + one-line reason |
| 2 | **Fit score & breakdown** | `DecisionExplanation.components` (base/freshness/semantic/overlay/learning) |
| 3 | **Missing skills + learning cost** | `ResumeDeltaEngine.generate_delta` (strong/missing/transferable, LOW/MED/HIGH) |
| 4 | **Resume recommendation** | `ResumeRouter.route` (AI/FDE/generic + reason + scores) |
| 5 | **Interview probability** | v1: bucket priors from `learning` (submitted→interview by role_family × resume_profile × score band); fallback default 0.12 |
| 6 | **Salary assessment** | Job comp_min/max vs `expected_ctc_lpa`/`expected_comp_usd`; market benchmark (knowledge store) → within/above/below |
| 7 | **Estimated effort** | `{fields, pages, ats_type, auto_fillable_frac, estimated_minutes}`; heuristic per ATS type; ~40s assisted target |
| 8 | **Likely screening questions** | Question corpus by ATS type + description keywords → top-N with pre-resolved answers (Answer Bank) |
| 9 | **Application strategy** | `auto\|ats\|manual\|unsupported` + reason (ADR-004 mapping) |
| 10 | **Risk flags** | expired, duplicate, `avoid_technologies`, `deal_breakers`, suspicious posting, company red flags, low-confidence provenance |
| 11 | **Provenance summary** | which fields are parser/provider/llm/human; overall brief confidence |
| 12 | **Context / intelligence trace** | pipeline path (`explain_decision`), score history, prior attempts |

## 3. Generation Pipeline

```
get_brief(opportunity_id):
  1. cache hit → return
  2. load opportunity + reconciled status
  3. deterministic components: fit score, resume delta, salary, effort, strategy, risk
  4. interview probability from learning priors (no LLM)
  5. LLM only for: likely-questions enrichment, prose summary (one pass, temp 0, cached)
  6. provenance + confidence assembly
  7. persist copilot_briefs; emit brief.generated event
```

## 4. Verdict Rule (deterministic)

- **Skip**: any deal_breaker/avoid_technology hit; expired; duplicate applied; fit_score < quality_threshold (default 68).
- **Apply**: fit_score ≥ threshold AND no risk blocker AND salary ≥ lower band.
- **Consider**: otherwise.

## 5. Confidence & Trust

- Each section carries `source` (deterministic/llm/knowledge) and `confidence`.
- Sections with `llm` provenance render with a distinct marker; the user can collapse to "only show what CareerFlow is certain about."
- Every number (fit, probability, salary band) is traceable to its inputs.

## 6. Effort Estimator (frozen heuristics)

- Known ATS: Greenhouse/Lever/Ashby = expected field count ranges (from adapter form-model history); Workday/Rippling = high + guidance mode.
- Unknown/generic: infer from description length + detected form on first assistant pass (v2).
- `estimated_minutes = fields * 0.4 + pages * 1.2`, floored, capped, labeled "assisted estimate".

## 7. Success Criteria

- Brief builds in < 5s cold, < 100ms cached.
- User accepts verdict ≥ 80% of the time (metric: `16_SUCCESS_METRICS.md`).
- Interview probability calibration: predicted band vs actual rate within ±5pp over 30+ outcomes.
