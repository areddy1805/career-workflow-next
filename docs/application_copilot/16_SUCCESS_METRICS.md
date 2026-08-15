# Success Metrics

**Last Updated:** 2026-08-02

| # | Metric | Target | How measured | Gate |
|---|---|---|---|---|
| M01 | Median assisted apply time | < 30s (Tier 1+2) | session timestamps (start→submit), manual audit | v5.1.0 |
| M02 | Brief verdict acceptance | ≥ 80% | user action follows verdict | v5.2.0 |
| M03 | Answer Bank auto-resolve rate | ≥ 90% screening questions | resolution source stats | v5.2.0 |
| M04 | Auto-answer correction rate | < 5% | user edits of auto answers | v5.2.0 |
| M05 | Funnel conversion SUBMITTED→INTERVIEW | improving q/q | lifecycle reconciliation | v5.2.0 |
| M06 | Fabricated claims | 0 | guardrail audit + manual review | v5.1.0 |
| M07 | Pipeline accounting regressions | 0 | ledger consistency suite | v5.1.0 |
| M08 | Field auto-fill rate | ≥ 85% | assistant fills | v5.1.0 |
| M09 | Interview-probability calibration | ±5pp over 30+ outcomes | predicted vs actual | v5.3.0 |
| M10 | LLM resolution calls | declining q/q | answerbank cache stats | v5.3.0 |
| M11 | Effort saved | reported | est. manual − assisted | v5.2.0 |
| M12 | Brief cold/cached latency | <5s / <100ms | perf suite | v5.1.0 |
| M13 | UI a11y | WCAG AA, 100% keyboard | a11y checklist | v5.1.0 |
| M14 | System uptime of assistant sessions | ≥ 99% no-crash | controller metrics | v5.2.0 |
