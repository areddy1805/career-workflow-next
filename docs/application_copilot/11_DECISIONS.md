# Decision Log

Non-ADR operational decisions + reversals. Architectural decisions live in `13_ADR/`.

| # | Date | Decision | Rationale | Status |
|---|---|---|---|---|
| D-001 | 2026-08-02 | UI routes flat under `/copilot/…`, matching existing `App.tsx` pattern | Consistency; zero new routing infra | Active |
| D-002 | 2026-08-02 | Assistant embeds a visible browser view (iframe/page preview) rather than an opaque headless driver | Trust + takeover (ADR-002) | Active |
| D-003 | 2026-08-02 | Submission confirmation uses hold-to-confirm gesture | Deliberate human gesture (ADR-002) | Active |
| D-004 | 2026-08-02 | `copilot.db` is the sole Copilot store; no new JSON state files | Matches "ledger is truth" rule | Active |
| D-005 | 2026-08-02 | Interview probability v1 = bucket priors, no ML model; revisit at ≥30 outcomes | Determinism-first (AGENTS.md) | Active |
| D-006 | 2026-08-02 | Autopilot (opt-in per-session submit) deferred to v5.2.0 | Risk control; assist-first v1 | Deferred |
| D-007 | 2026-08-02 | Screenshot/email ingestion adapters deferred to backlog | Scope control (ADR-004) | Deferred |
| D-008 | 2026-08-02 | `copilot.db` schema implements the 10 tables of frozen §7.8 exactly; the “11 tables” count in CP-0-02's AC (08_IMPLEMENTATION_PLAN.md) is a miscount — no 11th table exists in any design doc | Documentation wins: §7.8 is the frozen interface; schema versioned via `PRAGMA user_version` (no bookkeeping table in the frozen set); no ADR needed (interface unchanged) | Active |
| D-009 | 2026-08-02 | `ParsedOpportunity` (ingestion §7.1) carries an optional `meta: dict` in addition to the frozen `data` + `provenance` | §7.1 pins “normalized dict + field provenance”; guidance flags such as LinkedIn paywall's `needs_manual_verify` (CP-1-05 AC) have no home in `data` (would break `CopilotOpportunity(**data)`). `meta` is additive, defaults to `{}`, and is surfaced by the ingest API as `guidance` | Active |
| D-011 | 2026-08-02 | Session transition matrix (CP-4-01) reads the frozen §7.5 event list as: `FORM_FILLING`/`CHECKPOINT_PENDING` are progress events that self-loop (no state advance); `HUMAN_SUBMIT` is the trigger `FORM_FILLED → SUBMITTED` and `SUBMITTED` is the CopilotEvent emitted on that transition — never a trigger; `OUTCOME_RECORDED` self-loops on `SUBMITTED` (outcome is data in §7.8 `outcome`/`outcome_at`, not a state) | §7.5 lists events without distinguishing triggers from emissions. If `SUBMITTED` were a second parallel trigger, ADR-002's human-gesture requirement would be bypassable at the machine level; making the gesture the trigger keeps it enforceable. `SESSION_CREATED` is valid only from the pre-creation sentinel (`None` state) | Active |

Reversals: none. Superseded: none.
