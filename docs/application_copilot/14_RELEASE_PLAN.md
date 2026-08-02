# Release Plan

**Last Updated:** 2026-08-02 (v5.1.0 alpha shipped)

## v5.1.0 — Copilot Alpha (SHIPPED 2026-08-02, tag `v5.1.0-alpha`)
**Scope (all certified):** PH0–PH8 complete — Tier 1 ingestion, Brief, Answer Bank, Session, Browser assist (visible browser, form model, resolver, checkpoints, recovery, ATS adapters, safety+audit), full Copilot UI (Inbox/Workspace/Brief/Assistant/History/Analytics/Learning/Settings + a11y polish), Learning system (outcome store, signals, bounded bias, answer weighting, tracking), Analytics (`/api/copilot/analytics` + telemetry).
**Gates:** PH0–PH8 checkpoints green; Phase G CI green (unit+integration+browser e2e+regression+perf+security guards); regression **1522**; coverage 93%; frontend `npm run gate` green; `<30s` assisted-apply demo is **manual** (pending user sample, carried caveat).
**Flags (all OFF by default):** `BROWSER_ENABLED`, `OUTCOME_CAPTURE_ENABLED`, `LEARNING_BIAS_ENABLED` — rollback = leave off, pipeline untouched (ADR-007).
**Rollback:** disable flags; tag revert.
**Known gaps:** autopilot deferred (v5.2.0, D-006); ≥85% auto-fill + <30s demo are manual-sample metrics pending user feedback; M02/M06/M07/M12/M13/M14 return null-with-note in analytics; email ingestion / screenshot OCR / Workday-Rippling polish deferred.

## v5.2.0 — Copilot Beta
Adds: Learning System live (bounded bias), Analytics, History depth, ATS adapter accuracy calibration (BK-010), optional autopilot (BK-004, opt-in).
**Gates:** PH7–PH8 checkpoints green; calibration targets; 30+ outcomes for model revisit.

## v5.3.0 — Copilot GA
Adds: Workday/Rippling assisted polish (Tier 3), email ingestion (BK-002), screenshot OCR (BK-001, optional), resume customization (BK-005, optional), SaaS/multi-tenant evaluation (BK-008 decision).
**Gates:** full `16_SUCCESS_METRICS.md` targets; security review; release checklist.
