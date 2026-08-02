# CareerFlow Application Copilot — Master Plan

**Version:** 5.1.0-rc1
**Last Updated:** 2026-08-02
**Status:** Design Approved — Implementation Pending

---

## Vision

CareerFlow discovers opportunities. The Application Copilot converts every opportunity from any source into a <30-second, high-quality, evidence-grounded application — and learns from every outcome to get better.

```
Discovery Engine → Application Copilot → Career Operating System
```

## Non-Negotiable Principles

1. **Assist-first, human submits.** The Copilot pre-fills and coaches; the human is the final authority on submission. (ADR-002)
2. **Normalize then execute.** Every source normalizes into ONE `CopilotOpportunity`; the Browser Assistant operates only on the normalized model. ATS adapters are optimizations, never architectural dependencies. (ADR-005)
3. **Intelligence before execution.** The Application Brief is the product. Automation is a delivery mechanism. (ADR-013)
4. **Never couple to the production pipeline.** The Copilot reads the pipeline through stable interfaces and writes outcomes only via existing repository APIs. (ADR-007)
5. **Truthfulness is a feature.** Answers are generated from evidence with verified/positionable/unsupported status, guardrails, and confidence thresholds — never fabricated. (ADR-009)
6. **Learn in production.** Every outcome feeds ranking, answers, and strategy. (ADR-011)
7. **Local-first, single-user v1, SaaS-ready design.** (ADR-006, ADR-010)

## Frozen Architectural Decisions

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Product thesis: Assist-first Application Copilot | ✅ Frozen |
| ADR-002 | Assist-first, human-submit execution model | ✅ Frozen |
| ADR-003 | Local backend agent (Playwright via FastAPI) | ✅ Frozen |
| ADR-004 | Source tiering (Tier 1/2/3) | ✅ Frozen |
| ADR-005 | Source-agnostic Browser Assistant on normalized model | ✅ Frozen |
| ADR-006 | Single-user v1, SaaS-ready design | ✅ Frozen |
| ADR-007 | Copilot ↔ pipeline decoupling (read-only + repo-API writes) | ✅ Frozen |
| ADR-008 | Canonical `CopilotOpportunity` + field provenance | ✅ Frozen |
| ADR-009 | Answer Bank built on `HybridQuestionResolver` | ✅ Frozen |
| ADR-010 | Local-first SQLite (`copilot.db`) | ✅ Frozen |
| ADR-011 | Greenfield persisted Learning System | ✅ Frozen |
| ADR-012 | Lifecycle reconciliation via read view (`JobLifecycleStore` canonical) | ✅ Frozen |
| ADR-013 | Brief is the product; execution is delivery | ✅ Frozen |

Full ADR bodies: `13_ADR/`.

## Source Scope (ADR-004)

| Tier | Sources | Mode |
|---|---|---|
| Tier 1 (Must) | Manual Queue, Generic Job URL, LinkedIn URL, Wellfound URL, Company Careers URL, Pasted JD text, PDF JD | Normalize + assist |
| Tier 2 (Native) | Greenhouse, Lever, Ashby | ATS adapters (optimizations) |
| Tier 3 (Assist-only) | Workday, Rippling | Checkpoint/guidance only |
| Not in v1 | LinkedIn auto-submit, Workday autonomous, bulk automation | Explicit non-goal |

## Roadmap / Milestones

| Milestone | Phase | Description | Status |
|---|---|---|---|
| M0 | PH0 | Foundations & Interface Freeze | ⏳ Pending |
| M1 | PH1 | Ingestion & Opportunity Normalization (Tier 1) | ⏳ Pending |
| M2 | PH2 | Application Brief Engine | ⏳ Pending |
| M3 | PH3 | Answer Bank | ⏳ Pending |
| M4 | PH4 | Application Session | ⏳ Pending |
| M5 | PH5 | Browser Assistant | ⏳ Pending |
| M6 | PH6 | Copilot UI | ⏳ Pending |
| M7 | PH7 | Learning System | ⏳ Pending |
| M8 | PH8 | Analytics & Success Metrics | ⏳ Pending |
| M9 | PH9 | Hardening, Testing, Release v5.1.0 | ⏳ Pending |

## Critical Path

PH0 → PH1 → PH2 → PH4 → PH6 → PH9. PH3 and PH5 run parallel to PH2/PH4; PH7/PH8 follow PH4. (Full graph: `08_IMPLEMENTATION_PLAN.md` §Dependency Graph.)

## Document Index

| File | Purpose |
|---|---|
| `00_MASTER_PLAN.md` | Entry point, roadmap, index (this file) |
| `01_PRODUCT_VISION.md` | Product design: vision, users, JTBD, pain, competitors, differentiators, risks |
| `02_ARCHITECTURE.md` | Subsystems, boundaries, data flow, state ownership, frozen interfaces |
| `03_OPPORTUNITY_MODEL.md` | Canonical source-independent opportunity model |
| `04_BROWSER_ASSISTANT.md` | Assistant capabilities, architecture, HITL, confidence, safety |
| `05_APPLICATION_BRIEF.md` | Brief content, generation, scoring |
| `06_ANSWER_BANK.md` | Answer storage, generation, confirmation, personalization |
| `07_UI.md` | Navigation, pages, keyboard-first workflow |
| `08_IMPLEMENTATION_PLAN.md` | Phase → Epic → Story → Atomic Task, dependency graph, risks, checkpoints |
| `09_TASK_BOARD.md` | Tracked task board (all tasks, statuses) |
| `10_PROGRESS.md` | Progress tracking (updated every session) |
| `11_DECISIONS.md` | Decision log (non-ADR decisions + reversals) |
| `12_BACKLOG.md` | Future work, ideas, tech debt |
| `13_ADR/` | Frozen architectural decision records (ADR-001…013 + INDEX) |
| `14_RELEASE_PLAN.md` | v5.1.0 alpha → v5.2.0 beta → v5.3.0 GA |
| `15_TESTING_PLAN.md` | Test strategy + phase gates |
| `16_SUCCESS_METRICS.md` | Metrics, targets, measurement |

## Related Documents

- `docs/ARCHITECTURE.md` — Production pipeline (frozen; Copilot reads from it)
- `AGENTS.md` — Engineering principles (Copilot must satisfy: deterministic-first, no silent regressions, telemetry preserved, small changes)
