# Career Workflow Architecture Specification

Version: **v1.0.0-RC1**  
Author: Career Workflow Engineering Team

---

## 1. Architectural Overview

**Career Workflow** is a policy-driven, multi-stage application orchestration system designed for automated job discovery, candidate-aware AI qualification, diversity-controlled selection, direct/questionnaire application execution, and transactionally persistent lifecycle accounting.

The core architecture follows a **Staged Pipeline Pattern** decoupled from storage and presentation through an **Event Bus** and a **FastAPI Control Plane**, powering a **React Operations Console**.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            OPERATIONS CONSOLE UI                            │
│                        (React 18 + Vite + Tailwind)                         │
└──────────────────────┬──────────────────────────────────────────────────────┘
                       │ REST / WebSockets
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI CONTROL PLANE                            │
│                             (api/routes.py)                                 │
└──────────────────────┬──────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CAREER WORKFLOW PIPELINE ENGINE                      │
│                                                                             │
│   ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐    │
│   │ 1. ACQUISITION   ├────►│ 2. CLASSIFICATION├────►│  3. SELECTION    │    │
│   │ Naukri + JobSpy  │     │ LLM Fit Scoring  │     │ Budget & Diversity│   │
│   └──────────────────┘     └──────────────────┘     └────────┬─────────┘    │
│                                                              │              │
│   ┌──────────────────┐     ┌──────────────────┐              │              │
│   │  6. ACCOUNTING   │◄────┤  5. RESOLUTION   │◄─────────────┘              │
│   │ SQLite Ledger    │     │ Deterministic/LLM│  4. APPLICATION ROUTING │
│   └──────────────────┘     └──────────────────┘                             │
└──────────────────────┬──────────────────────────────────────────────────────┘
                       │ Event Notifications
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EVENT BUS & PROJECTIONS                            │
│  ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐  │
│  │ Metrics Projection   │ │ Explorer Projection  │ │ Trace Projection     │  │
│  └──────────────────────┘ └──────────────────────┘ └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Components & Subsystems

### 2.1 ExecutionContext & Pipeline Orchestration
- **`CareerWorkflowPipeline`** (`src/orchestration/pipeline.py`): The main orchestrator executing discrete stages sequentially.
- **`ExecutionContext`**: Thread-safe runtime context holding pipeline configuration, search parameters, execution run ID, active stage state, metrics collector, and event bus emitters.

### 2.2 Dual Provider Job Acquisition
- **`JobAcquisitionManager`** (`src/search/`): Coordinates job fetching across configured sources.
- **`NaukriClient`** (`src/client/`): Authenticated API integration for Naukri platform job search, detailed job description retrieval, and direct application.
- **`JobSpyProvider`** (`src/acquisition/jobspy_provider.py`): Unauthenticated multi-board scraper supporting Indeed, LinkedIn, Glassdoor, and Google Jobs. Converts Pandas DataFrames into internal immutable dataclasses immediately upon acquisition to isolate Pandas dependencies from core code.

### 2.3 AI Job Classifier & Selection Budget Engine
- **`JobFilterPipeline2`** (`src/client/job_classifier.py`): Evaluates job postings against candidate stack, hard negative filters (forbidden locations, unwanted tech stacks), and candidate experience.
- **`OMLXClient`** (`src/llm/client.py`): Local-first OpenAI-compatible HTTP client communicating with local LLM servers (oMLX/vLLM/Ollama) to generate 0–100 candidate fit scores.
- **`SelectionEngine`**: Enforces selection capacity budgets ($N$ jobs per run) and multi-level diversity constraints (capping applications per company, role family, or vacancy).

### 2.4 Hybrid Questionnaire Resolver & Application Router
- **`ApplicationRouter`** (`src/application/router.py`): Inspects selected jobs and routes them to appropriate execution handlers (direct API submit, external ATS link preservation, or manual action queue).
- **`QuestionResolver`** (`src/resolution/`): Evaluates application dynamic questionnaires via candidate evidence profiles (`config/candidate_evidence.py`). Uses deterministic rule matching first, falling back to local LLM resolution for complex open-ended prompts.

### 2.5 SQLite Application Ledger & Terminal Accounting
- **`ApplicationLedger`** (`src/application/ledger.py`): Transactional SQLite store (`data/application_ledger.db`) keeping an immutable history of application attempts, timestamps, response codes, and terminal states (`APPLIED`, `REJECTED`, `EXPIRED`, `SKIPPED`).
- **Terminal Accounting Validator**: Ensures every job passing through selection reaches a valid terminal state without silent drops or dangling states.

### 2.6 Intelligent Dual-Tier Caching Layer
- **`CacheManager`** (`src/cache/cache_manager.py`):
  1. **Job Search Cache**: Caches raw search acquisition responses to prevent redundant web/API scraping.
  2. **LLM Fingerprint Cache** (`src/cache/fingerprint.py`): Hashes job description text + prompt version to cache AI fit scores, saving LLM compute resources on repeated runs.

### 2.7 Observability, Event Bus & Projections
- **`EventBus`** (`src/orchestration/metrics.py`): In-memory event publisher broadcasting execution events (`JobAcquired`, `JobScored`, `JobSelected`, `ApplicationAttempted`, `TerminalStateReached`).
- **Projections**:
  - **Metrics Projection**: Real-time aggregation of funnel conversion rates, latency, and success ratios.
  - **Explorer Projection**: Structured run artifacts saved to `artifacts/runs/<run_id>/`.
  - **Trace Projection**: Detailed diagnostic event logs for post-run inspection.

### 2.8 Control Plane API & React Operations Console
- **FastAPI Backend** (`api/routes.py`): RESTful control plane exposing dashboard metrics, live run status, job application history, manual action queues, and system health endpoints.
- **React Operations Console** (`frontend/`): Modern Vite + React single-page application providing an interactive control panel for running pipelines, reviewing job cards, monitoring queues, and viewing system telemetry.

---

## 3. Data Flow & Job State Transitions

```text
 ┌───────────────┐
 │   ACQUIRED    │  Job fetched from Naukri or JobSpy
 └───────┬───────┘
         │
         ▼
 ┌───────────────┐
 │  CLASSIFIED   │  AI scored & checked against negative filters
 └───────┬───────┘
         │
         ├─────────────────────────┐
         │ (Passed Score & Budget) │ (Failed Score or Budget Limit)
         ▼                         ▼
 ┌───────────────┐         ┌───────────────┐
 │   SELECTED    │         │   REJECTED    │ [TERMINAL STATE]
 └───────┬───────┘         └───────────────┘
         │
         ▼
 ┌───────────────┐
 │  ROUTED/APPLY │  Routed to Direct API, Questionnaire, or Manual Queue
 └───────┬───────┘
         │
         ├───► ┌───────────────┐
         │     │    APPLIED    │ [TERMINAL STATE]
         │     └───────────────┘
         │
         ├───► ┌───────────────┐
         │     │    FAILED     │ [TERMINAL STATE]
         │     └───────────────┘
         │
         └───► ┌───────────────┐
               │    SKIPPED    │ [TERMINAL STATE]
               └───────────────┘
```

---

## 4. Verification & Hardening Principles

1. **No Code Duplication**: Core business logic resides in `src/`, with `api/` serving as thin HTTP wrapper routes.
2. **DataFrame Isolation**: Pandas is restricted strictly within `JobSpyProvider` internal processing and never leaks into `src/orchestration` or `src/application`.
3. **Strict Universal Links**: Raw URLs and direct apply links are preserved across all data transformations.
4. **Idempotence**: Application ledger checks prevent duplicate applications to the same job posting ID across runs.
