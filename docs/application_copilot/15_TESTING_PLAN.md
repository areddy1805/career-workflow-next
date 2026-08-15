# Testing Plan

**Last Updated:** 2026-08-02

## 1. Test Strategy (test-before-code)

| Type | Tooling | Covers | Where |
|---|---|---|---|
| Unit | pytest | state machines, fingerprinting, verdict/provenance, resolver order, metrics math | `tests/copilot/unit/` |
| Integration | pytest + fixture DBs | stores, adapters (fixtures), API contract, status view, outcome→ledger | `tests/copilot/integration/` |
| Browser | Playwright (headed-off in CI) | form model on fixture pages, fill, checkpoints, recovery, ATS adapters | `tests/copilot/browser/` |
| End-to-end | Playwright + FastAPI test client | ingest→brief→session→assistant→submit→outcome (mock external) | `tests/copilot/e2e/` |
| Manual | checklist | <30s demo, keyboard, takeover, empty/loading/error | `16_CHECKLISTS` (doc) |
| Performance | pytest-benchmark / manual | cold brief <5s, cached <100ms, polls, single browser | `tests/copilot/perf/` |
| Regression | existing suite + new | ledger/accounting regression (CP-4-04), ranking at bias=0 (CP-7-03), pipeline untouched | `tests/` root |

## 2. Ground Rules

1. Every atomic task ships tests with its DoD (see `08_IMPLEMENTATION_PLAN.md`).
2. LLM calls mocked in unit/integration; live LLM only in opt-in manual suites.
3. No test hits the network by default (fixtures); URL adapters use fixtures.
4. Ledger-consistency regression is a **hard gate** for any outcome-writing task.
5. Ranking regression must be green at `learning_bias = 0` before bias ships.

## 3. Phase Gates (must pass to call phase complete)

| Phase | Required green |
|---|---|
| PH0 | unit: enums/settings/db/events · integration: health |
| PH1 | unit: fingerprint/provenance · integration: adapters on fixtures, dedup matrix, status view, ingest API |
| PH2 | unit: verdict matrix, salary, effort, probability · integration: brief store/cache/API |
| PH3 | unit: fingerprint/synonyms, resolution order, confirm transitions, profile isolation · integration: answer API |
| PH4 | unit: session transitions · integration: workspace, outcome→ledger + **ledger regression** |
| PH5 | browser: form model fixtures, fill, checkpoints, recovery, safety invariant · integration: assistant API |
| PH6 | manual: keyboard/a11y/workspace demo · build green |
| PH7 | unit: signals, bias bounds, answer weighting · integration: outcome reconcile · **ranking regression at bias=0** |
| PH8 | unit/integration: all metric definitions |
| PH9 | full CI (unit+integration+browser+e2e+regression+perf+security) |

## 4. Manual Validation Checklist (per release)
- Ingest each Tier-1 source → Brief within 5s.
- <30s assisted apply on Greenhouse sample.
- Take-over mid-fill; Esc abort; guidance mode on DOM drift.
- Answer Bank: confirm/lock/edit; profile switch atomic.
- Ledger/accounting counts unchanged by Copilot sessions.
- Empty/loading/error states on every Copilot page; keyboard coverage.
