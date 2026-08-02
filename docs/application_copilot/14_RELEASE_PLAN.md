# Release Plan

**Last Updated:** 2026-08-02

## v5.1.0 — Copilot Alpha (target: after PH0–PH6)
**Scope:** Tier 1 ingestion, Brief, Answer Bank, Session, Browser assist, UI (Inbox/Workspace/Brief/Assistant/History), accounting-safe outcome capture.
**Gates:** PH0–PH6 checkpoints green; accounting regression suite green; `<30s` demo on Greenhouse sample; a11y checklist green.
**Flags:** all Copilot features behind flags, **off by default**; browser submission assist-only.
**Rollback:** disable flags; pipeline unaffected (ADR-007).
**Known gaps:** no learning bias, no analytics polish, autopilot off.

## v5.2.0 — Copilot Beta
Adds: Learning System live (bounded bias), Analytics, History depth, ATS adapter accuracy calibration (BK-010), optional autopilot (BK-004, opt-in).
**Gates:** PH7–PH8 checkpoints green; calibration targets; 30+ outcomes for model revisit.

## v5.3.0 — Copilot GA
Adds: Workday/Rippling assisted polish (Tier 3), email ingestion (BK-002), screenshot OCR (BK-001, optional), resume customization (BK-005, optional), SaaS/multi-tenant evaluation (BK-008 decision).
**Gates:** full `16_SUCCESS_METRICS.md` targets; security review; release checklist.
