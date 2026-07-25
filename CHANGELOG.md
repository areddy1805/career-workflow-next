# Changelog

All notable changes to **Career Workflow** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - Platform Engineering Release

### Unified Reporting & Runtime ViewModel
- **Unified Reporting**: Implemented comprehensive system telemetry and subtrack metrics into a `Pipeline Intelligence` artifact.
- **Runtime ViewModel**: Deployed a clean separation between database storage (`Decision Ledger`) and live presentation state to improve React UI performance.

---

## [1.1.0] - Operations Console & Provider Platform

### Operations Console
- **16-Surface Operations Console**: Shipped a unified React interface featuring Pipeline Control, Jobs Workspace, Inbox, Analytics, Ledger Explorer, System Health, and more.
- **Decision Ledger**: Standardized the core data model into a SQLite WAL-backed authoritative ledger replacing transient JSON state stores.

### Provider Platform & DeepSeek Integration
- **Multi-Provider Acquisition**: Supported seamless job discovery across Naukri and JobSpy (Indeed, LinkedIn, Google).
- **Inference Platform**: Centralized AI evaluations via `ProviderManager` with support for local OMLX routing and robust **DeepSeek integration**.
- **Cost Analytics**: Added precise token-level tracking to measure deterministic savings against hypothetical LLM costs.

---

## [1.0.0] - Rich CLI & Pipeline Intelligence

### Rich Typer CLI
- **Rich CLI**: Introduced a comprehensive Typer-based command-line interface (`cw`) for system execution, validation (`cw doctor`), and artifact inspection (`cw inspect`).

### Semantic Intelligence & Learning Platform
- **Candidate Intelligence**: Grounded AI qualification scoring by evaluating job descriptions against candidate profiles, certifications, and past experience constraints.
- **Semantic Intelligence & Rules Filtering**: Configurable pipeline rules allowing complex transition-role eligibility scoring and Posting Age Policy constraints.
- **Learning Platform**: Captured historical decisions and application outcomes into an evaluation set for future model fine-tuning.

---

## [0.5.0] - Resilience & Runtime State

### Runtime State & Observability
- **Event Bus & Metrics Projection**: Shifted from direct invocation to an event-driven telemetry model, decoupling execution logic from analytics.
- **Runtime State**: Enforced strict locking and state transition validations via the `Runtime State Manager` ensuring crash recovery and consistent artifact snapshots.
- **Production Hardening**: Added robust fallback logic for provider rate limits, network timeouts, and captcha challenges during headless automation.

---

## [0.1.0] - Foundation

### Initial Pipeline
- **Job Classifier & AI Fit Scoring**: Initial system for parsing role relevance using local AI models.
- **Selection Budget**: Hard limits ensuring application constraints such as `MAX_APPLICATIONS_PER_COMPANY_PER_RUN`.
- **Hybrid Questionnaire Resolver**: Engine for interacting with arbitrary Applicant Tracking System screening forms.

