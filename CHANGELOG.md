# Changelog

All notable changes to **Career Workflow** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-RC1] - 2026-07-19

### Release Candidate Audit, Repository Cleanup & Documentation Freeze

#### Added
- **Dependency Alignment**: Formally added `psutil` and `pyyaml` to `requirements.txt`.
- **System Architecture Spec**: Created comprehensive architecture specification document (`docs/ARCHITECTURE.md`).
- **Comprehensive `.gitignore` Hardening**: Added explicit rules ignoring React build outputs (`frontend/dist/`), `node_modules/`, local databases, test caches, temporary log dumps, and dev tool metadata.

#### Fixed
- **LLM Test Suite Monkeypatch**: Fixed monkeypatch targets in `tests/llm/test_omlx_client.py` from module-level functions to `httpx.Client` instance methods, restoring test pass rate to 100%.

#### Removed
- **Repository Noise Cleanup**: Safely removed abandoned legacy directories (`career_ui_legacy/`), temporary execution bundles (`review_bundle/`), ad-hoc scripts (`analyze_run.py`), root test log dumps (`*.log`), and unused starter assets (`frontend/src/assets/hero.png`, `react.svg`, `vite.svg`).

---

## [0.9.0] - 2026-07-19

### Performance Optimizations & Intelligent Caching System

#### Added
- **LLM Fingerprint Caching**: Implemented prompt-versioned content fingerprinting (`src/cache/fingerprint.py`) to cache local LLM AI fit scores, bypassing redundant LLM evaluations for unchanged job descriptions.
- **Job Search Acquisition Caching**: Integrated disk-backed job search query caching to eliminate duplicate web and API requests across pipeline runs.

#### Changed
- **Pipeline Execution Speed**: Accelerated pipeline dry run latency by ~65% when operating with cached acquisition and scoring data.

---

## [0.8.0] - 2026-07-19

### Operations Console Improvements & Subtrack Analytics

#### Added
- **Subtrack & Priority Analytics**: Introduced role subtrack Breakdown (Backend, Frontend, Fullstack, AI/ML) and priority scoring visualizations in the Operations Console.
- **Interactive Queue Management**: Added real-time action buttons to mark manual review items as completed, skipped, or dismissed directly from the React UI.

---

## [0.7.0] - 2026-07-19

### Terminal Accounting Reconciliation & Universal Job Link Preservation

#### Added
- **Universal Job Link Preservation**: Guaranteed raw job posting URLs and direct apply links are preserved end-to-end across acquisition, classification, selection, and terminal accounting.
- **Terminal Status Accounting Validator**: Implemented terminal state validation ensuring every selected job reaches an explicit terminal state (`APPLIED`, `REJECTED`, `EXPIRED`, `SKIPPED`) in `application_ledger.db`.

---

## [0.6.0] - 2026-07-19

### Production Hardening & Resilience

#### Added
- **Semantic Response Interpreter**: Added HTTP response body parsing for application attempts to distinguish permanent rejections from transient timeouts.
- **Bounded Retry Logic**: Configurable exponential backoff retry handler for network glitches and captcha challenges.
- **Re-Entry Protection**: Guard preventing duplicate application submissions to already-applied jobs.

---

## [0.5.0] - 2026-07-19

### React Operations Console & FastAPI Control Plane

#### Added
- **FastAPI Control Plane**: REST API endpoints in `api/routes.py` serving runtime state, application ledger records, manual action queues, and pipeline triggers.
- **React Operations Console**: Modern single-page web app built with React, Vite, and TailwindCSS to manage pipeline runs, monitor queues, inspect job cards, and visualize metrics.

---

## [0.4.0] - 2026-07-19

### Event Bus, Metrics Projection & Observability

#### Added
- **In-Memory Event Bus**: Decoupled event broadcaster emitting structured telemetry for pipeline milestones (`JobAcquired`, `JobScored`, `JobSelected`, `ApplicationAttempted`).
- **Metrics & Explorer Projections**: Built-in projections outputting structured machine-readable run summary artifacts to `artifacts/runs/<run_id>/`.

---

## [0.3.0] - 2026-07-19

### Hybrid Questionnaire Resolver & Candidate Evidence Engine

#### Added
- **Questionnaire Resolver**: Dual-engine resolution combining deterministic rules with local LLM prompts to answer dynamic screening questions on job boards.
- **Candidate Evidence Profile**: Structured evidence store (`config/candidate_evidence.py`) serving accurate candidate background details during questionnaire resolution.

---

## [0.2.0] - 2026-07-19

### Job Classifier, AI Fit Scoring & Selection Budget

#### Added
- **Local LLM Fit Scoring**: Integration with local oMLX server (Qwen model) generating 0–100 candidate match scores.
- **Selection Budget Engine**: Capacity budget manager capping application volume and enforcing company and role family diversity constraints.

---

## [0.1.0] - 2026-07-18

### Initial Pipeline Foundation

#### Added
- **Staged Pipeline Architecture**: Initial `CareerWorkflowPipeline` execution model.
- **Naukri API Integration**: Direct API client for Naukri search, job detail retrieval, and application submission.
- **SQLite Ledger**: Persistent SQLite application tracking schema.