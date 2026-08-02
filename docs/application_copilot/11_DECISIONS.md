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

Reversals: none. Superseded: none.
