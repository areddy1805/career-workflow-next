# Task Board

**Last Updated:** 2026-08-02
**View:** Jira-style

## Keys
Priority: Critical / High / Medium / Low. Status: TODO / IN PROGRESS / DONE / BLOCKED / CANCELLED.

## PH0 — Foundations
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-0-01 | Scaffold copilot package | Critical | DONE | — | S | 2h |
| CP-0-02 | copilot.db schema + migrations | Critical | DONE | 0-01 | M | 4h |
| CP-0-03 | CopilotEvent model + emitter | High | DONE | 0-02 | S | 2h |
| CP-0-04 | Copilot API router + health | Critical | DONE | 0-02 | S | 2h |
| CP-0-05 | Frontend Copilot shell | High | DONE | 0-04 | M | 4h |

## PH1 — Ingestion
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-1-01 | Ingestion interface + registry + pipeline | Critical | DONE | 0-01 | M | 4h |
| CP-1-02 | Text/HTML/PDF/URL extraction utils | Critical | DONE | 1-01 | M | 6h |
| CP-1-03 | Manual queue adapter | Critical | DONE | 1-01 | S | 2h |
| CP-1-04 | Generic URL adapter | Critical | DONE | 1-02 | M | 6h |
| CP-1-05 | LinkedIn URL adapter | High | DONE | 1-02 | M | 4h |
| CP-1-06 | Wellfound URL adapter | High | DONE | 1-02 | M | 4h |
| CP-1-07 | Careers URL adapter | High | DONE | 1-04 | M | 4h |
| CP-1-08 | Pasted text adapter | High | DONE | 1-02 | M | 6h |
| CP-1-09 | PDF adapter | High | DONE | 1-02,1-08 | M | 4h |
| CP-1-10 | CopilotOpportunity model | Critical | DONE | 0-01 | M | 4h |
| CP-1-11 | Opportunity store + dedup + mapping | Critical | DONE | 1-10,0-02 | M | 6h |
| CP-1-12 | Status read view | High | DONE | 1-11 | M | 4h |
| CP-1-13 | Ingest/list/detail API | Critical | DONE | 1-01,1-11 | M | 6h |

## PH2 — Brief
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-2-01 | Brief assembler | Critical | DONE | 1-11 | M | 6h |
| CP-2-02 | Salary assessment | High | DONE | 2-01 | S | 3h |
| CP-2-03 | Effort estimator | Medium | DONE | 2-01 | S | 3h |
| CP-2-04 | Interview probability v1 | High | DONE | 2-01,7-01 | S | 3h |
| CP-2-05 | Likely questions | Medium | DONE | 2-01,3-02 | M | 5h |
| CP-2-06 | LLM prose augmentation | Medium | DONE | 2-01 | M | 4h |
| CP-2-07 | Brief store + cache + API | Critical | DONE | 2-01,1-13 | M | 4h |

## PH3 — Answer Bank
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-3-01 | Question fingerprinting | Critical | DONE | 0-01 | M | 5h |
| CP-3-02 | Resolution engine wrapper + cache | Critical | DONE | 3-01 | M | 6h |
| CP-3-03 | Answer store CRUD + profiles | Critical | DONE | 3-01,0-02 | M | 6h |
| CP-3-04 | Confirmation workflow | High | DONE | 3-03 | M | 4h |
| CP-3-05 | Profile switching | High | DONE | 3-03 | S | 3h |
| CP-3-06 | Answer bank API | High | DONE | 3-04,3-05 | M | 4h |

## PH4 — Session
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-4-01 | Session state machine | Critical | DONE | 0-03 | S | 3h |
| CP-4-02 | Session persistence + events | Critical | DONE | 4-01,0-02 | S | 3h |
| CP-4-03 | Workspace service | Critical | DONE | 4-02,2-07,3-02 | M | 8h |
| CP-4-04 | Outcome capture | Critical | DONE | 4-03 | M | 5h |
| CP-4-05 | Session API | High | DONE | 4-03 | S | 3h |

## PH5 — Browser Assistant
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-5-01 | Browser controller | Critical | DONE | 0-01 | M | 6h |
| CP-5-02 | Form field model | Critical | DONE | 5-01 | H | 10h |
| CP-5-03 | Field resolver | Critical | DONE | 5-02,3-02 | M | 6h |
| CP-5-04 | Checkpoint engine | High | DONE | 5-03 | M | 5h |
| CP-5-05 | Recovery | High | DONE | 5-02 | M | 5h |
| CP-5-06 | ATS adapters | High | DONE | 5-02 | M | 8h |
| CP-5-07 | Safety + audit | Critical | DONE | 5-01 | M | 5h |
| CP-5-08 | Assistant API + events | High | DONE | 5-04,5-07 | M | 6h |

## PH6 — UI
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-6-01 | Inbox | Critical | DONE | 1-13,2-07 | M | 8h |
| CP-6-02 | Brief view | High | DONE | 2-07 | S | 5h |
| CP-6-03 | Workspace wizard | Critical | DONE | 4-05,6-02 | H | 12h |
| CP-6-04 | Assistant panel | Critical | TODO (ready) | 5-08,6-03 | H | 12h |
| CP-6-05 | History | Medium | TODO (ready) | 4-05 | S | 5h |
| CP-6-06 | Analytics page | Medium | TODO | 8-01 | M | 8h |
| CP-6-07 | Learning page | Medium | TODO | 3-06,7-03 | M | 8h |
| CP-6-08 | Settings | Medium | TODO | 0-01 | S | 4h |
| CP-6-09 | Keyboard + a11y + polish | High | TODO | 6-01..08 | M | 8h |

## PH7 — Learning
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-7-01 | Outcome store + reconcile | Critical | TODO | 4-04 | M | 5h |
| CP-7-02 | Signal collection | High | TODO | 7-01 | M | 5h |
| CP-7-03 | Ranking feedback (bias) | High | TODO | 7-02 | H | 10h |
| CP-7-04 | Answer weighting | Medium | TODO | 7-01 | S | 3h |
| CP-7-05 | Provider/ATS success | Medium | TODO | 7-01 | S | 3h |
| CP-7-06 | Interview/offer tracking | High | TODO | 7-01 | M | 6h |

## PH8 — Analytics
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-8-01 | Funnel + effort metrics | High | TODO | 1-11,4-04 | M | 6h |
| CP-8-02 | Answer + learning health | Medium | TODO | 3-06,7-03 | M | 5h |
| CP-8-03 | Telemetry + analytics API | High | TODO | 8-01,8-02 | M | 5h |

## PH9 — Hardening & Release
| ID | Task | Pri | Status | Dep | Cplx | Effort |
|---|---|---|---|---|---|---|
| CP-9-01 | Regression + e2e suite | Critical | TODO | all | H | 12h |
| CP-9-02 | Security review | Critical | TODO | 9-01 | M | 6h |
| CP-9-03 | Performance tuning | High | TODO | 9-01 | M | 6h |
| CP-9-04 | Docs freeze + release notes | High | TODO | 9-01..03 | S | 3h |
| CP-9-05 | Release v5.1.0 alpha | Critical | TODO | 9-04 | S | 2h |
