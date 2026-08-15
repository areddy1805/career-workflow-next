# CareerFlow Application Copilot — Product Vision

**Version:** 5.1.0
**Last Updated:** 2026-08-02
**Status:** Approved (ADR-001, ADR-013)

---

## Elevator Pitch

Every job opportunity CareerFlow discovers — from Naukri, LinkedIn, an email from a recruiter, a pasted PDF, or a Greenhouse link — becomes a <30-second, high-quality application. The Copilot reads the job, tells you whether it's worth your time (the Brief), fills every form field truthfully from your verified evidence (the Answer Bank), picks the right resume, drives the browser up to the final click, and tracks what happens after — then gets smarter from every interview and offer.

## Product Thesis

**Application is a decision problem, not a typing problem.** The competitor set solves typing (autofill). CareerFlow solves decisions: *should I apply, how should I position, what will they ask, what's my probability, what did I learn.* Automation (browser pre-fill) is the delivery vehicle for decisions already made. (ADR-001, ADR-013)

## Target Users

1. **The Operator (primary, v1)** — the solo user running a high-volume, high-quality search, 2 active profiles (AI / Forward-Deployed), a verified evidence base, and a production pipeline already discovering opportunities.
2. **Power users (secondary)** — early adopters with the same profile shape.
3. **Future tenants (designed-in, not shipped)** — multi-profile, then multi-user. ADR-006.

## Primary Workflows

| # | Workflow | Entry → Exit | Keyboard path |
|---|---|---|---|
| W1 | Inbox triage | Any source → normalized opportunity → Brief → Apply / Skip / Dismiss | `1` open brief, `a` apply, `s` skip, `d` dismiss |
| W2 | Guided apply | Brief → answers reviewed → resume selected → form pre-filled → human submits → outcome captured | `j/k` navigate, `enter` advance, `space` confirm |
| W3 | Answer bank curation | Review generated answers → confirm/lock/edit per profile | `e` edit, `c` confirm, `l` lock |
| W4 | Outcome review | Post-submission lifecycle → interview/offer feedback | `o` open history |
| W5 | Learning review | Signals → ranking bias → strategy recalibration | `l` learning |

## Jobs-to-be-Done

1. "I found a job (anywhere) — apply without 20 minutes of form-filling."
2. "Tell me if this job is worth my time before I invest."
3. "Answer the recruiter's screening questions truthfully and well."
4. "Use the right resume, tailored to this role."
5. "Track what happens after I apply, and make my next applications better."
6. "Keep my identity/compensation/experience facts consistent across every ATS."

## Pain Points (today)

- Manual ATS forms: 5–20 min each; ~60% of effort is re-typing the same facts.
- Duplicate re-entry: notice period, CTC, experience-years asked repeatedly, worded differently.
- Resume ambiguity: which of AI/FDE fits; no per-job emphasis.
- Questionnaire wording traps: combined technologies, exact-metric asks, sensitive fields — answered wrong or refused, losing applications.
- No post-application loop: outcomes not tracked, so the pipeline never learns.
- Sources are fragmented: manual queue, emails, PDFs, links all require separate handling.

## Success Metrics (targets in `16_SUCCESS_METRICS.md`)

- Median assisted apply time < 30s on Tier 1 + Tier 2 sources.
- Brief recommendation accepted ≥ 80%.
- Answer Bank auto-resolve ≥ 90% of screening questions; auto-answer correction rate < 5%.
- Funnel conversion (SUBMITTED→INTERVIEW) improves quarter-over-quarter.
- Zero fabricated claims (guardrail audit).
- Zero pipeline accounting regressions (ledger consistency tests).

## Competitive Landscape

| Player | Strength | Gap CareerFlow exploits |
|---|---|---|
| Simplify / generic autofill extensions | Fast generic pre-fill | No evidence grounding, no truth guardrails, no per-job intelligence |
| Teal / Jobscan | Resume/ATS parsing | No live application execution, no answer bank |
| LinkedIn Easy Apply | One-click in-platform | Platform lock-in; low quality; no post-apply loop |
| "Apply bots" (LazyApply et al.) | Bulk volume | Spam reputation, account bans, no personalization |
| ATS-native (Greenhouse/Lever/Ashby) | Native forms | Each is one island; no unified intelligence across them |
| **CareerFlow Copilot** | **Evidence-grounded answers + Brief + source-agnostic execution + learning loop** | **Truthfulness + intelligence + unified execution** |

## Unique Differentiators

1. **Guardrailed evidence engine** — answers grounded in verified/positionable/unsupported evidence (`CANDIDATE_EVIDENCE`), never fabricated. The moat.
2. **The Application Brief** — interview probability, effort, likely questions, risk, resume call — before you spend a second.
3. **Source-agnostic execution** — one model, one assistant, 15+ sources.
4. **Closed learning loop** — offer/interview/reject feedback into ranking and answers.
5. **Local-first, private** — PII and resumes stay on your machine.

## Risks (summary; full matrix in `08_IMPLEMENTATION_PLAN.md` §Risks)

| Risk | Mitigation |
|---|---|
| ATS ToS / account ban | Assist-first; human submits; rate limits; cooldowns (ADR-002) |
| Browser fragility | Normalize-then-execute; DOM model versioning; recovery; guidance-mode degrade (ADR-005) |
| LLM fabrication | Existing evidence constraints + shape validation + confidence gates (ADR-009) |
| Scope creep across sources | Tiering; adapter pattern; v1 = Tier 1 + Tier 2 (ADR-004) |
| PII/resume security | Local-first SQLite; sensitive fields stay manual (ADR-010) |
| Pipeline accounting regression | Write outcomes only via existing repo APIs; ledger consistency tests (ADR-007) |

## Non-Goals (v1)

- Autonomous submission against Workday/Rippling/LinkedIn.
- Bulk mass-apply.
- Multi-user SaaS, auth, cloud sync.
- Rewriting any frozen pipeline system.
- Resume template generation (manual PDFs remain source of truth).
