# Implementation Plan

**Version:** 5.1.0-rc1
**Status:** Approved — executable

---

## 1. Method

Phase → Epic → Story → **Atomic Task**. Every atomic task is independently completable in one coding session, with objective, scope, files, dependencies, acceptance criteria, test strategy, rollback, DoD, complexity, and effort. Task IDs are `CP-{phase}-{seq}`.

## 2. Dependency Graph

```
PH0 Foundations ──► PH1 Ingestion ──► PH2 Brief ──► PH4 Session ──► PH6 UI ──► PH9 Release
                        │                │
                        │                └──► PH3 Answer Bank ──► PH5 Browser ──┘
                        │                                                    │
                        └────────────────────────────────────────► PH7 Learning ─► PH8 Analytics
```

**Critical path:** PH0 → PH1 → PH2 → PH4 → PH6 → PH9.
**Independently schedulable (parallel):** PH3 (Answer Bank) can start immediately after PH0, in parallel with PH1/PH2. PH5 (Browser) can start after PH3 answers + PH0, in parallel with PH4. PH7/PH8 follow PH4. UI (PH6) has two parallel tracks: Inbox/Brief (after PH1/PH2 APIs) and Workspace/Assistant (after PH4/PH5 APIs).

Epic-level dependency table:

| Epic | Depends on |
|---|---|
| FND (PH0) | — |
| ING, SRC, OPP, API (PH1) | FND |
| BRI (PH2) | OPP |
| ANS (PH3) | FND (parallel to PH1/PH2) |
| SES (PH4) | OPP, BRI, ANS |
| BRO (PH5) | ANS, FND (parallel to SES) |
| UIX (PH6) | API of PH1–PH5 |
| LRN (PH7) | SES (outcomes), ANS (quality) |
| ANL (PH8) | PH1, PH4, PH7 |
| HLD (PH9) | all |

## 3. Phases, Epics, Stories, Atomic Tasks

### PH0 — Foundations & Interface Freeze (critical path start)

**Epic FND — Package & persistence foundation.**

**Story FND-1: Copilot package skeleton.**
- `CP-0-01` **Scaffold `src/copilot/` package** — `__init__.py`, `constants.py` (source enum, strategies, statuses), `exceptions.py`, `config/loader.py`.
  - Dep: none · Cplx: S · Risk: L · Effort: 2h
  - Scope: package + enums + settings loader reading `config/copilot.yaml`.
  - Files: `src/copilot/{__init__,constants,exceptions}.py`, `src/copilot/config/loader.py`, `config/copilot.yaml`.
  - AC: package imports cleanly; enums match frozen interface §7; settings load with defaults.
  - Test: unit — enums/settings.
  - Rollback: revert commit; package is additive.
  - DoD: import + pytest green; no behavior change to pipeline.

**Story FND-2: `copilot.db` bootstrap.**
- `CP-0-02` **Schema + migration runner** — `schema.sql` (frozen §7.8), `db.py` (sqlite3 connection, WAL, migration runner), bootstrap on first use.
  - Dep: CP-0-01 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/db/schema.sql`, `src/copilot/db/db.py`, `src/copilot/db/migrate.py`.
  - AC: all 11 tables created; migrations idempotent; WAL enabled.
  - Test: unit — create/migrate/rollback-of-schema file.
  - Rollback: delete DB file (dev) / schema is additive.
  - DoD: tables verified via introspection; fresh + migrated paths tested.

**Story FND-3: Event contracts.**
- `CP-0-03` **CopilotEvent model + emitter** — event types (namespaced), emitter writing to `copilot_events` + logger.
  - Dep: CP-0-02 · Cplx: S · Risk: L · Effort: 2h
  - Files: `src/copilot/events/{models,emitter}.py`.
  - AC: emit persists row + logs; trace_id propagates.
  - Test: unit — emitter.
  - Rollback: additive.
  - DoD: event round-trip tested.

**Story FND-4: API + frontend scaffolding.**
- `CP-0-04` **Copilot API router + health** — `api/routers/copilot.py`, mount in `api/main.py`, `/api/copilot/health`, Pydantic request models in `api/schemas.py`.
  - Dep: CP-0-02 · Cplx: S · Risk: L · Effort: 2h
  - Files: `api/routers/copilot.py`, `api/main.py`, `api/schemas.py`.
  - AC: health returns subsystem status; CORS consistent.
  - Test: integration — GET health.
  - Rollback: remove router mount.
  - DoD: endpoint live; response convention `{ok,data,error}`.
- `CP-0-05` **Frontend Copilot shell** — nav group, routes, placeholder pages (empty state only, non-functional), `lib/api/copilot.ts`, `store/copilot.ts` skeleton, TS types (`lib/types/copilot.ts`).
  - Dep: CP-0-04 · Cplx: M · Risk: L · Effort: 4h
  - Files: `frontend/src/App.tsx`, `frontend/src/pages/copilot/*.tsx`, `frontend/src/lib/api/copilot.ts`, `frontend/src/lib/hooks.ts`, `frontend/src/store/copilot.ts`, `frontend/src/lib/types/copilot.ts`.
  - AC: routes render empty states; nav badge wired to health; ⌘K entries present.
  - Test: manual (oxlint + build).
  - Rollback: revert route block.
  - DoD: `npm run build` passes; no dead imports.

**Epic FND exit gate (PH0 checkpoint):** package boots, DB migrates, events flow, API+UI shells live.

---

### PH1 — Ingestion & Opportunity Normalization (Tier 1)

**Epic ING — Ingestion framework.**
- `CP-1-01` **IngestionAdapter interface + registry + pipeline** (frozen §7.1); payload model; error taxonomy (unsupported/parse/timeout/unresolvable).
  - Dep: CP-0-01 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/ingestion/{base.py,registry.py,pipeline.py,models.py}`.
  - AC: adapter_for dispatches; pipeline returns ParsedOpportunity or typed error.
  - Test: unit — registry, error mapping.
  - Rollback: additive; pipeline not invoked yet.
  - DoD: adapter simulation test green.
- `CP-1-02` **Text extraction utilities** — HTML→text (strip scripts/styles), meta/JSON-LD extraction, URL fetch with timeout/robots/UA, PDF text extraction (pypdf), text normalization (whitespace, unicode).
  - Dep: CP-1-01 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/ingestion/{fetcher.py,extract/html.py,extract/pdf.py,extract/text.py,extract/jsonld.py}`.
  - AC: fixtures for html/pdf/url parse; timeouts enforced.
  - Test: unit + integration with fixture files.
  - Rollback: additive.
  - DoD: extraction fixtures green.

**Epic SRC — Source adapters (Tier 1).**
- `CP-1-03` **Manual queue adapter** — reads `WorkflowQueue`/`ManualActionQueue` rows → opportunity (source=`manual_queue`).
  - Dep: CP-1-01 · Cplx: S · Risk: L · Effort: 2h
  - Files: `src/copilot/ingestion/adapters/manual_queue.py`.
  - AC: existing queue items appear as opportunities with provenance `provider`.
  - Test: integration against seeded queue DB.
  - Rollback: adapter not registered = no-op.
  - DoD: seeded queue → opportunity verified.
- `CP-1-04` **Generic URL adapter** — fetch → meta/JSON-LD/OG → description; canonical_url; fallback LLM structing only on deterministic fail (confidence-gated).
  - Dep: CP-1-02 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/ingestion/adapters/generic_url.py`.
  - AC: known job-page fixtures normalize; fields have provenance.
  - Test: integration fixtures + 1 live URL (opt-in).
  - Rollback: unregister.
  - DoD: fixture suite green.
- `CP-1-05` **LinkedIn URL adapter** — fetch + parse; paywall/limited → partial + guidance flag; never auto-submit (ADR-004).
  - Dep: CP-1-02 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/ingestion/adapters/linkedin_url.py`.
  - AC: parse fixture; paywall path yields partial opportunity + `needs_manual_verify`.
  - Test: unit fixture.
  - Rollback: unregister.
  - DoD: fixture green.
- `CP-1-06` **Wellfound URL adapter** — fetch + parse.
  - Dep: CP-1-02 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/ingestion/adapters/wellfound_url.py`.
  - Test: unit fixture.
  - Rollback: unregister.
  - DoD: fixture green.
- `CP-1-07` **Careers page adapter** — wraps generic_url + careers heuristics (job board detection, apply link resolution).
  - Dep: CP-1-04 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/ingestion/adapters/careers_url.py`.
  - Test: unit fixture.
  - Rollback: unregister.
  - DoD: fixture green.
- `CP-1-08` **Pasted text adapter** — structured via rules (title/company/salary/skills extraction) + optional confidence-gated LLM.
  - Dep: CP-1-02 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/ingestion/adapters/pasted_text.py`.
  - Test: unit fixtures (multiple JD formats).
  - Rollback: unregister.
  - DoD: fixtures green; LLM path cached.
- `CP-1-09` **PDF adapter** — PDF→text→same rules as pasted_text.
  - Dep: CP-1-02, CP-1-08 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/ingestion/adapters/pdf.py`.
  - Test: unit fixtures (scanned→guidance; text→normal).
  - Rollback: unregister.
  - DoD: fixtures green.

**Epic OPP — Opportunity model & store.**
- `CP-1-10` **CopilotOpportunity dataclass + serialization + provenance + fingerprint** (frozen contract `03_OPPORTUNITY_MODEL.md`).
  - Dep: CP-0-01 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/oppstore/model.py`.
  - AC: to_dict/from_dict round-trip; fingerprint stable; provenance enforced.
  - Test: unit — round-trip, fingerprint, immutability.
  - Rollback: additive.
  - DoD: contract tests green.
- `CP-1-11` **Opportunity store CRUD + dedup + source↔pipeline mapping** — upsert on fingerprint; merge superseded; `pipeline_job_id` mapping to ledger.
  - Dep: CP-1-10, CP-0-02 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/oppstore/store.py`.
  - AC: upsert dedups; mapping resolves; richer record wins.
  - Test: unit + integration (in-memory DB).
  - Rollback: additive.
  - DoD: dedup/merge tests green.
- `CP-1-12` **Status read view** (ADR-012) — reconcile `JobLifecycleStore` + `WorkflowQueue` + ledger stage → `status_view`.
  - Dep: CP-1-11 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/oppstore/status_view.py`.
  - AC: mapping table correct for all reconciliation cases.
  - Test: unit with simulated states.
  - Rollback: additive.
  - DoD: reconciliation matrix green.

**Epic API — Ingestion/opportunity API.**
- `CP-1-13` **Ingest + list + detail endpoints** — POST `/api/copilot/ingest` (source payload), GET `/opportunities`, GET `/opportunities/{id}`.
  - Dep: CP-1-01, CP-1-11 · Cplx: M · Risk: M · Effort: 6h
  - Files: `api/routers/copilot.py`, `api/schemas.py`.
  - AC: ingest any Tier-1 payload → opportunity; errors typed; pagination.
  - Test: integration.
  - Rollback: additive.
  - DoD: API contract tests green.

**PH1 exit gate:** Tier-1 sources normalize; opportunities persisted/deduped; status view accurate.

---

### PH2 — Application Brief

**Epic BRI.**
- `CP-2-01` **Brief assembler** — deterministic aggregation: verdict, fit breakdown, resume rec, missing skills, strategy, risk; `ApplicationBrief` dataclass (`05_APPLICATION_BRIEF.md`).
  - Dep: CP-1-11 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/brief/{models.py,assembler.py}`.
  - AC: all deterministic sections present with provenance; verdict rule correct.
  - Test: unit (verdict matrix).
  - Rollback: additive.
  - DoD: verdict matrix green.
- `CP-2-02` **Salary assessment service** — job range vs profile target; market benchmark from knowledge store; within/above/below.
  - Dep: CP-2-01 · Cplx: S · Risk: L · Effort: 3h
  - Files: `src/copilot/brief/salary.py`.
  - AC: classification correct for fixture ranges.
  - Test: unit.
  - Rollback: additive.
  - DoD: unit green.
- `CP-2-03` **Effort estimator** — ATS-type heuristics + field-count estimate → minutes.
  - Dep: CP-2-01 · Cplx: S · Risk: L · Effort: 3h
  - Files: `src/copilot/brief/effort.py`.
  - Test: unit.
  - Rollback: additive.
  - DoD: unit green.
- `CP-2-04` **Interview probability v1** — bucket priors from learning store (role_family × resume_profile × score band); default fallback; no LLM.
  - Dep: CP-2-01, CP-7-01 (priors table) · Cplx: S · Risk: M · Effort: 3h
  - Files: `src/copilot/brief/probability.py`.
  - AC: priors read; default 0.12 when cold.
  - Test: unit.
  - Rollback: additive.
  - DoD: calibration tests defined.
- `CP-2-05` **Likely questions service** — ATS-type + description keywords + corpus → top-N with pre-resolved answers (Answer Bank).
  - Dep: CP-2-01, CP-3-02 · Cplx: M · Risk: M · Effort: 5h
  - Files: `src/copilot/brief/questions.py`.
  - Test: unit.
  - Rollback: additive.
  - DoD: corpus query green.
- `CP-2-06` **LLM prose augmentation (optional, gated)** — one cached pass for summary/prose only; temp 0; provenance `llm`.
  - Dep: CP-2-01 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/brief/llm.py`.
  - AC: gated, cached, budget-respected.
  - Test: unit (mocked LLM).
  - Rollback: feature-flag off.
  - DoD: flag off by default; tests green.
- `CP-2-07` **Brief persistence + cache + endpoints** — `copilot_briefs`, `build/get/invalidate`, GET `/opportunities/{id}/brief`.
  - Dep: CP-2-01, CP-0-02, CP-1-13 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/brief/{store.py,api.py}`.
  - AC: build cold <5s, cached <100ms; invalidate works.
  - Test: integration.
  - Rollback: additive.
  - DoD: API + cache tests green.

**PH2 exit gate:** every opportunity has a complete, cached Brief; verdict accepted ≥80% (manual sample).

---

### PH3 — Answer Bank (parallel track)

**Epic ANS.**
- `CP-3-01` **Question fingerprinting + canonical labels** — normalize → canonical slot; registry; synonym coverage.
  - Dep: CP-0-01 · Cplx: M · Risk: M · Effort: 5h
  - Files: `src/copilot/answerbank/{fingerprint.py,canonical.py}`.
  - AC: variant phrasings → same slot; stable hash.
  - Test: unit (synonym table).
  - Rollback: additive.
  - DoD: synonym suite green.
- `CP-3-02` **Resolution engine wrapper** — wraps `HybridQuestionResolver` + stored-answer first + caching; `AnswerResolution` (§7.4).
  - Dep: CP-3-01 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/answerbank/{resolver.py,cache.py}`.
  - AC: resolution order frozen §3; cached generated answers.
  - Test: unit + integration (mocked LLM).
  - Rollback: additive.
  - DoD: resolution-order tests green.
- `CP-3-03` **Answer store CRUD + profiles** — `copilot_answers` ops; per-profile namespace; confirm/lock; supersede.
  - Dep: CP-3-01, CP-0-02 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/answerbank/store.py`.
  - AC: namespace isolation; confirm/lock semantics.
  - Test: unit + integration.
  - Rollback: additive.
  - DoD: CRUD + isolation tests green.
- `CP-3-04` **Confirmation workflow + override** — status transitions auto→confirm→confirmed/locked; human override stored as `human`.
  - Dep: CP-3-03 · Cplx: M · Risk: M · Effort: 4h
  - Files: `src/copilot/answerbank/confirm.py`.
  - AC: transitions validated; override wins.
  - Test: unit.
  - Rollback: additive.
  - DoD: state tests green.
- `CP-3-05` **Profile switching service** — atomic namespace + resume mapping swap.
  - Dep: CP-3-03 · Cplx: S · Risk: M · Effort: 3h
  - Files: `src/copilot/answerbank/profiles.py`.
  - AC: atomic swap; no cross-leak.
  - Test: unit.
  - Rollback: additive.
  - DoD: unit green.
- `CP-3-06` **Answer bank API** — list/get/update/confirm/lock/switch.
  - Dep: CP-3-04, CP-3-05 · Cplx: M · Risk: M · Effort: 4h
  - Files: `api/routers/copilot.py`, `api/schemas.py`.
  - AC: contract §7.9.
  - Test: integration.
  - Rollback: additive.
  - DoD: API tests green.

**PH3 exit gate:** ≥90% of screening questions resolve; confirmed answers persist per profile.

---

### PH4 — Application Session

**Epic SES.**
- `CP-4-01` **Session state machine** — frozen states/events; transition validation.
  - Dep: CP-0-03 · Cplx: S · Risk: L · Effort: 3h
  - Files: `src/copilot/session/{state_machine.py,models.py}`.
  - AC: all valid/invalid transitions tested.
  - Test: unit.
  - Rollback: additive.
  - DoD: transition matrix green.
- `CP-4-02` **Session persistence + events** — `copilot_sessions`, `copilot_session_events`.
  - Dep: CP-4-01, CP-0-02 · Cplx: S · Risk: L · Effort: 3h
  - Files: `src/copilot/session/{store.py,events.py}`.
  - AC: state + snapshot persisted; events appended.
  - Test: integration.
  - Rollback: additive.
  - DoD: green.
- `CP-4-03` **Workspace service** — orchestrates brief→answers→resume→assistant→submit→outcome; resume rec integration (`ResumeRouter`, `ResumeDelta`).
  - Dep: CP-4-02, CP-2-07, CP-3-02 · Cplx: M · Risk: M · Effort: 8h
  - Files: `src/copilot/session/service.py`.
  - AC: workspace advances correctly; snapshots consistent.
  - Test: integration.
  - Rollback: additive.
  - DoD: happy-path integration green.
- `CP-4-04` **Outcome capture** — interpret submission result; write pipeline-visible outcome **only via** `WorkflowQueue.transition` / ledger APIs (ADR-007); emit learn signal.
  - Dep: CP-4-03 · Cplx: M · Risk: H · Effort: 5h
  - Files: `src/copilot/session/outcome.py`.
  - AC: no direct pipeline DB writes; accounting consistent; ledger tests pass.
  - Test: integration + ledger consistency.
  - Rollback: feature-flag; nothing breaks if disabled.
  - DoD: accounting regression suite green.
- `CP-4-05` **Session API** — create/get/advance/abort.
  - Dep: CP-4-03 · Cplx: S · Risk: L · Effort: 3h
  - Files: `api/routers/copilot.py`.
  - AC: contract §7.9.
  - Test: integration.
  - Rollback: additive.
  - DoD: API green.

**PH4 exit gate:** end-to-end session (brief→answers→resume→submit→outcome) runs without pipeline regressions.

---

### PH5 — Browser Assistant (parallel track)

**Epic BRO.**
- `CP-5-01` **Browser controller** — Playwright session, visible browser, launch/teardown, takeover hook.
  - Dep: CP-0-01 (adds `playwright` dep) · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/browser/controller.py`.
  - AC: launches, navigates, closes; one session at a time.
  - Test: integration (headed=False in CI).
  - Rollback: feature-gated.
  - DoD: navigation smoke green.
- `CP-5-02` **Form field model** — DOM/a11y → `FormModel` (typed fields, pages, options, required).
  - Dep: CP-5-01 · Cplx: H · Risk: H · Effort: 10h
  - Files: `src/copilot/browser/form/model.py`.
  - AC: fixture HTML pages → correct typed fields.
  - Test: integration fixtures (greenhouse/lever/ashby sample pages).
  - Rollback: feature-gated.
  - DoD: fixture suite green.
- `CP-5-03` **Field resolver** — field→fingerprint→Answer Bank→typed fill + confidence.
  - Dep: CP-5-02, CP-3-02 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/browser/resolver.py`.
  - AC: type matching (select/radio/checkbox/date) correct.
  - Test: unit.
  - Rollback: additive.
  - DoD: unit green.
- `CP-5-04` **Checkpoint engine** — frozen gates (`04_BROWSER_ASSISTANT.md` §6/§7).
  - Dep: CP-5-03 · Cplx: M · Risk: M · Effort: 5h
  - Files: `src/copilot/browser/checkpoint.py`.
  - AC: gates trigger correctly; never bypass submit.
  - Test: unit.
  - Rollback: additive.
  - DoD: gate matrix green.
- `CP-5-05` **Recovery** — DOM rescan, retry/backoff, guidance fallback.
  - Dep: CP-5-02 · Cplx: M · Risk: M · Effort: 5h
  - Files: `src/copilot/browser/recovery.py`.
  - AC: drift→rebuild→guidance within one retry.
  - Test: integration (simulated drift).
  - Rollback: additive.
  - DoD: recovery fixtures green.
- `CP-5-06` **ATS adapters (Greenhouse/Lever/Ashby)** — field semantics optimization; generic fallback intact.
  - Dep: CP-5-02 · Cplx: M · Risk: M · Effort: 8h
  - Files: `src/copilot/browser/adapters/{greenhouse,lever,ashby}.py`.
  - AC: adapter never required; accuracy improves.
  - Test: integration fixtures.
  - Rollback: unregister adapter.
  - DoD: adapter + fallback tests green.
- `CP-5-07` **Safety + audit** — read-only-until-submit invariant, PII rules, action audit.
  - Dep: CP-5-01 · Cplx: M · Risk: H · Effort: 5h
  - Files: `src/copilot/browser/safety.py`.
  - AC: audit rows for every action; sensitive fields never auto-filled; human gesture required for submit.
  - Test: unit + security review.
  - Rollback: feature-gated.
  - DoD: safety invariant tests green.
- `CP-5-08` **Assistant API + events** — open/form/fill/checkpoint/confirm/submit/guidance/abort; browser.* events.
  - Dep: CP-5-04, CP-5-07 · Cplx: M · Risk: M · Effort: 6h
  - Files: `api/routers/copilot.py`, `src/copilot/browser/api.py`.
  - AC: contract §7.6.
  - Test: integration.
  - Rollback: additive.
  - DoD: API green.

**PH5 exit gate:** ≥85% field auto-fill on Tier 1/Tier 2; human submits; safety audit complete.

---

### PH6 — UI

**Epic UIX.**
- `CP-6-01` **Inbox** — unified queue, filters, keyboard triage, Brief sheet.
  - Dep: CP-1-13, CP-2-07 · Cplx: M · Risk: M · Effort: 8h
  - Files: `frontend/src/pages/copilot/Inbox.tsx`, components.
  - AC: triage actions work; shortcuts; empty/loading/error states.
  - Test: manual + component tests (vitest if added).
  - Rollback: route-additive.
  - DoD: a11y + build green.
- `CP-6-02` **Brief view** — 12 sections, provenance chips, "certain facts" filter.
  - Dep: CP-2-07 · Cplx: S · Risk: L · Effort: 5h
  - Files: `frontend/src/pages/copilot/Brief.tsx`.
  - AC: renders all sections; CTA→apply.
  - Test: manual.
  - Rollback: additive.
  - DoD: build green.
- `CP-6-03` **Workspace wizard** — 5 steps, answer review/edit, resume select, keyboard-first.
  - Dep: CP-4-05, CP-6-02 · Cplx: H · Risk: M · Effort: 12h
  - Files: `frontend/src/pages/copilot/Apply.tsx`, `store/copilot.ts`.
  - AC: wizard completes end-to-end; answers editable; shortcuts.
  - Test: manual + component.
  - Rollback: additive.
  - DoD: full flow manual pass.
- `CP-6-04` **Assistant panel** — embedded view, field list, checkpoints, take-over.
  - Dep: CP-5-08, CP-6-03 · Cplx: H · Risk: H · Effort: 12h
  - Files: `frontend/src/pages/copilot/Assistant.tsx`.
  - AC: live progress; checkpoint banners; take-over.
  - Test: manual + e2e (Playwright).
  - Rollback: additive.
  - DoD: manual <30s demo passes.
- `CP-6-05` **History** — sessions table + timeline.
  - Dep: CP-4-05 · Cplx: S · Risk: L · Effort: 5h
  - Files: `frontend/src/pages/copilot/History.tsx`.
  - AC: renders outcomes; drill-in.
  - Test: manual.
  - Rollback: additive.
  - DoD: build green.
- `CP-6-06` **Analytics page** — funnel, conversion, effort saved, answer health, calibration.
  - Dep: CP-8-01 · Cplx: M · Risk: M · Effort: 8h
  - Files: `frontend/src/pages/copilot/Analytics.tsx`.
  - AC: charts render real data.
  - Test: manual.
  - Rollback: additive.
  - DoD: build green.
- `CP-6-07` **Learning page** — answer editor, profile switch, evidence view, bias view.
  - Dep: CP-3-06, CP-7-03 · Cplx: M · Risk: M · Effort: 8h
  - Files: `frontend/src/pages/copilot/Learning.tsx`.
  - AC: confirm/lock/edit; atomic profile switch.
  - Test: manual.
  - Rollback: additive.
  - DoD: build green.
- `CP-6-08` **Settings** — thresholds, autopilot, sources, effort caps, LLM budget.
  - Dep: CP-0-01 · Cplx: S · Risk: L · Effort: 4h
  - Files: `frontend/src/pages/copilot/Settings.tsx`.
  - AC: persists via `config/copilot.yaml` + store.
  - Test: manual.
  - Rollback: additive.
  - DoD: build green.
- `CP-6-09` **Keyboard + a11y + polish pass** — full shortcut map, ARIA, states.
  - Dep: CP-6-01..08 · Cplx: M · Risk: M · Effort: 8h
  - Files: all copilot pages + shared components.
  - AC: 100% interactive elements keyboard-reachable; WCAG AA.
  - Test: a11y + manual.
  - Rollback: n/a.
  - DoD: a11y checklist green.

**PH6 exit gate:** all surfaces live; workspace <30s demo; a11y checklist green.

---

### PH7 — Learning System

**Epic LRN.**
- `CP-7-01` **Outcome store** — persisted outcomes; reconcile with existing ledger/lifecycle stages.
  - Dep: CP-4-04 · Cplx: M · Risk: M · Effort: 5h
  - Files: `src/copilot/learning/{store.py,models.py}`.
  - AC: outcome rows idempotent; reconciliation correct.
  - Test: unit + integration.
  - Rollback: additive.
  - DoD: reconciliation matrix green.
- `CP-7-02` **Signal collection** — outcome, answer quality, provider/ATS conversion, resume profile, age-at-apply.
  - Dep: CP-7-01 · Cplx: M · Risk: M · Effort: 5h
  - Files: `src/copilot/learning/signals.py`.
  - AC: signals derivable from stores.
  - Test: unit.
  - Rollback: additive.
  - DoD: green.
- `CP-7-03` **Ranking feedback** — persisted `learning_bias` (replaces in-memory `learning_bias=0.0` path); monotonic; explore/exploit; consumed by Brief probability + next-run ranking via existing bias hook.
  - Dep: CP-7-02 · Cplx: H · Risk: H · Effort: 10h
  - Files: `src/copilot/learning/bias.py`, wiring into `priority_engine` hook.
  - AC: bias only affects ranking within bounded range; flag-gated; existing ranking tests unchanged at bias=0.
  - Test: unit + ranking regression.
  - Rollback: flag off → identical to today.
  - DoD: regression + bias tests green.
- `CP-7-04` **Answer weighting** — outcome-quality feedback into `copilot_answers.outcome_quality`.
  - Dep: CP-7-01 · Cplx: S · Risk: L · Effort: 3h
  - Files: `src/copilot/learning/answer_quality.py`.
  - AC: weights update correctly.
  - Test: unit.
  - Rollback: additive.
  - DoD: green.
- `CP-7-05` **Provider/ATS success + routing preference** — conversion analytics feeding adapter/strategy preference.
  - Dep: CP-7-01 · Cplx: S · Risk: L · Effort: 3h
  - Files: `src/copilot/learning/provider_success.py`.
  - Test: unit.
  - Rollback: additive.
  - DoD: green.
- `CP-7-06` **Interview/offer tracking** — email + manual + server-status reconciliation (reuse `normalize_server_status`).
  - Dep: CP-7-01 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/learning/tracking.py`.
  - AC: lifecycle advances monotonically.
  - Test: integration.
  - Rollback: additive.
  - DoD: green.

**PH7 exit gate:** outcomes persist; ranking bias live but reversible; answer weighting active.

---

### PH8 — Analytics

**Epic ANL.**
- `CP-8-01` **Funnel + effort metrics** — ingested→briefed→applied→viewed→shortlisted→interview→offer; effort-saved.
  - Dep: CP-1-11, CP-4-04 · Cplx: M · Risk: M · Effort: 6h
  - Files: `src/copilot/analytics/funnel.py`.
  - Test: unit + integration.
  - Rollback: additive.
  - DoD: metric correctness tests green.
- `CP-8-02` **Answer bank + learning health metrics** — resolve rate, correction rate, LLM call trend, calibration.
  - Dep: CP-3-06, CP-7-03 · Cplx: M · Risk: M · Effort: 5h
  - Files: `src/copilot/analytics/health.py`.
  - Test: unit.
  - Rollback: additive.
  - DoD: green.
- `CP-8-03` **Telemetry export + metrics endpoints** — `/api/copilot/analytics`; events→metrics aggregation.
  - Dep: CP-8-01, CP-8-02 · Cplx: M · Risk: M · Effort: 5h
  - Files: `api/routers/copilot.py`, `src/copilot/telemetry/`.
  - Test: integration.
  - Rollback: additive.
  - DoD: API green.

**PH8 exit gate:** all `16_SUCCESS_METRICS.md` data points computable.

---

### PH9 — Hardening & Release

**Epic HLD.**
- `CP-9-01` **Regression + browser e2e suite** — full `15_TESTING_PLAN.md` Phase G.
  - Dep: all · Cplx: H · Risk: M · Effort: 12h
  - Files: `tests/copilot/`.
  - AC: suite green in CI.
  - Test: this IS the testing work.
  - Rollback: n/a.
  - DoD: CI green.
- `CP-9-02` **Security review** — PII handling, local-first audit, no secrets, dependency scan (playwright), no-pipeline-write invariant re-verified.
  - Dep: CP-9-01 · Cplx: M · Risk: H · Effort: 6h
  - AC: checklist green.
  - Test: security checklist.
  - Rollback: n/a.
  - DoD: review sign-off.
- `CP-9-03` **Performance tuning** — cold brief <5s, inbox 30s poll, session 1s poll, browser single-instance, LLM budget adherence.
  - Dep: CP-9-01 · Cplx: M · Risk: M · Effort: 6h
  - AC: perf targets met.
  - Test: perf suite.
  - Rollback: n/a.
  - DoD: targets met.
- `CP-9-04` **Documentation freeze + release notes** — update `10_PROGRESS.md`, `09_TASK_BOARD.md`, `11_DECISIONS.md`; write v5.1.0 notes in `14_RELEASE_PLAN.md`.
  - Dep: CP-9-01..03 · Cplx: S · Risk: L · Effort: 3h
  - AC: docs consistent.
  - Rollback: n/a.
  - DoD: cross-reference audit green.
- `CP-9-05` **Release v5.1.0 (Copilot alpha)** — go/no-go per `14_RELEASE_PLAN.md`; tag.
  - Dep: CP-9-04 · Cplx: S · Risk: M · Effort: 2h
  - AC: gate signed off.
  - Test: release checklist.
  - Rollback: tag revert; feature flags default off.
  - DoD: alpha shipped, flags off by default.

## 4. Risks per Phase + Mitigations

| Phase | Architectural | Technical | UX | Performance | Security | Mitigation |
|---|---|---|---|---|---|---|
| PH0 | Wrong schema freeze | Dep version drift | — | — | Secret in config | Schema reviewed against frozen §7; lock deps; secrets in env only |
| PH1 | Adapter explosion / tight coupling | PDF/HTML variance; LLM over-use | Bad normalization → bad Briefs | URL fetch hangs | Fetch SSRF/URL safety | Adapter pattern + registry; extraction fixtures; provenance; timeouts + allowlist; LLM gated/cached |
| PH2 | Brief contradicts pipeline scoring | Probability cold-start | Verdict wrong → distrust | LLM prose cost | — | Deterministic-first; calibration tests; flag off; budget via inference_budget |
| PH3 | Fingerprint collisions | Evidence drift | Auto answers corrected often | Cache growth | Sensitive answers | Canonical registry; re-fingerprint on evidence change; correction metric; sensitive class locked |
| PH4 | Outcome double-accounting | Session crash mid-flow | Lost workspace state | — | — | Writes only via repo APIs + ledger consistency tests; snapshot+resume; additive |
| PH5 | Assistant coupled to ATS | DOM fragility; CAPTCHA | Checkpoint fatigue | Concurrency | PII in DOM; browser risk | Normalize-then-execute (ADR-005); recovery+guidance; gate count; single-instance; audit + local-only |
| PH6 | UI scope creep | Untyped API layer | Keyboard inconsistency | Polling load | — | Page specs frozen; add shared TS types; a11y checklist; poll cadence caps |
| PH7 | Bias destabilizes ranking | Feedback loops oscillate | Opaque bias | — | — | Monotonic + bounded bias; flag-gated; explore/exploit; explainable view |
| PH8 | Metrics disagreement with pipeline | — | Confusing numbers | Aggregation cost | — | Reuse existing ledger metrics; single metric definitions |
| PH9 | Release with hidden flags | Flaky e2e | — | — | Supply chain | Flags off by default; CI must pass; dep scan |

## 5. Implementation Checkpoints (per phase)

Each phase ends with a formal gate:

| Phase | Deliverables | Verification | Success criteria | Go/No-Go |
|---|---|---|---|---|
| PH0 | package, DB, events, API+UI shells | pytest, build, health endpoint | package imports; DB migrates; health OK | All unit + integration green; health returns OK |
| PH1 | adapters, model, store, API | fixtures + integration | Tier-1 normalize; dedup; status view | fixture suite green; dedup matrix green |
| PH2 | Brief engine + cache + API | unit matrix + sample | verdict correct; build <5s cold | verdict matrix green; manual sample 10/10 sensible |
| PH3 | Answer Bank | unit + integration | ≥90% resolve; confirm flow | resolve-rate target met in fixture corpus |
| PH4 | Session + outcome | integration + accounting regression | end-to-end without pipeline regression | accounting regression suite green |
| PH5 | Assistant + adapters + safety | fixtures + e2e | ≥85% fill; human submit; audit | safety invariant + fill-rate green |
| PH6 | all pages | manual + a11y | workspace <30s demo; a11y AA | demo + checklist green |
| PH7 | learning | unit + ranking regression | bias bounded & reversible | regression green; bias flag off = today |
| PH8 | analytics | metric tests | all metrics computable | metric tests green |
| PH9 | release | full CI + checklist | v5.1.0 alpha shipped | go/no-go signed |
