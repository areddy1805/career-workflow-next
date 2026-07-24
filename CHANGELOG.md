# Changelog

All notable changes to **Career Workflow** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-07-24

### Career Workflow Operations Console Overhaul, Decision Ledger & Pipeline Intelligence

#### Added
- **Decision Ledger Infrastructure**: Implemented SQLite WAL-backed authoritative `Decision Ledger` (`src/orchestration/job_decision_ledger.py`, `/ledger`) with full transaction tracing, status transition auditing, and queryable search/filtering APIs.
- **Pipeline Intelligence & Explorer**: Introduced `Pipeline Intelligence` telemetry projections (`src/orchestration/pipeline_intelligence.py`, `/intelligence`) and `Pipeline Explorer` (`src/orchestration/pipeline_explorer.py`, `/explorer`) for interactive run decision trees, stage execution timelines, and diagnostic inspection.
- **Automated System Auditing Framework**: Built comprehensive system audit engine (`api/routers/audit.py`, `/audit`) that runs multi-phase diagnostics across components, AI integration, and application policies, outputting structured technical Markdown reports.
- **16-Surface Operations Console**: Expanded the React operations console with 16 dedicated pages (`Overview`, `Pipeline`, `Jobs`, `Decision Ledger`, `Applications`, `Inbox`, `Intelligence`, `Explorer`, `Audit`, `Runs`, `System Health`, `Configuration`, `Providers`, `Logs`, `Metrics`, `Developer Tools`).
- **Custom React Hooks**: Added modular frontend hooks (`useLedger`, `useAudit`, `usePipelineExplorer`, `useSystemHealth`, `useConfiguration`, `useProviders`) with automatic API data synchronization.
- **Posting Age Policy**: Integrated configurable job freshness threshold filtering (`JOB_POSTING_MAX_AGE_DAYS`, default 30 days) to deterministically reject stale job postings before evaluation (`src/client/posting_age_policy.py`).
- **Post-Score Guard**: Added output validation and score normalization guard (`src/orchestration/post_score_guard.py`) for AI candidate fit scoring outputs (`LLM Reviewed`).
- **InferenceRouter & Token Cost Control**: Introduced `InferenceRouter` and `InferenceService` (`src/llm/inference_router.py`) to manage LLM API costs, token budgets, and provider inference routing efficiently.
- **Single Candidate Architecture**: Consolidated search profile architecture into standard candidate categories with automated resume routing.
- **Multi-Provider Health Safeguards**: Added provider health monitoring and automatic degradation safeguards to prevent failing search providers from stalling execution runs.

#### Changed
- **API Routing Architecture**: Refactored backend into modular FastAPI routers (`api/routers/audit.py`, `ledger.py`, `providers.py`, `logs.py`, `developer.py`).
- **Data Fetching & State Synchronization**: Replaced monolithic component state fetching in React with clean, isolated custom hooks and React Query refetching.
- **Terminology Synchronization**: Standardized system terminology across code, APIs, UI, and documentation (`Career Workflow Operations Console`, `Decision Ledger`, `Pipeline Intelligence`, `Pipeline Explorer`, `LLM Reviewed`, `Detail Fetch`, `Qualified`, `Selected`, `Applications`, `Providers`).

#### Fixed
- **Duplicate Rejection Accounting**: Resolved terminal state duplicate tracking bug in rejected jobs accounting.
- **Pipeline Lock Cleanup**: Fixed lock file handling to support clean process recovery without manual lock file removal.
- **Test Mode Telemetry**: Ensured test mode execution properly records metric projections without mutating production database tables.

## [1.0.0-RC2] - 2026-07-23

### Unified CLI, Packaging Overhaul & Production Diagnostics

#### Added
- **Unified `cw` CLI**: Introduced a comprehensive Typer-based CLI (`cw`) wrapping all control plane operations (`run`, `schedule`, `doctor`, `inspect`, `report`, `monitor`).
- **Execution Replay**: Automated run capture preserving `pipeline.log`, `execution_manifest.json`, `environment.txt`, and `git.txt` within a unified artifact directory (`artifacts/runs/<run_id>/`).
- **Production Packaging**: Upgraded to PEP 517/518 build system via `pyproject.toml` and `setuptools.build_meta`, enabling seamless global installations (`pip install -e .`).
- **Production Diagnostics**: Upgraded `cw doctor` to serve as a robust CI pre-flight check, complete with proper exit codes, health summaries, and resolution of false-positive warnings.

#### Fixed
- **Duplicate Accounting Bug**: Fixed a persistent terminal state duplicate tracking bug in the ledger.
- **Packaging Import Hacks**: Removed all CWD-dependent `sys.path.insert()` hacks across the codebase through dynamic package discovery.
- **Stale Recovery Warnings**: Improved `cw doctor` logic to correctly recognize successful pipeline recoveries as healthy rather than degraded.

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