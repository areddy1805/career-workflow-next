# Changelog

All notable changes to **Career Workflow** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [4.0.0] - 2026-07-25

### Major Architectural Shift: Runtime v2 & Operations Center

v4.0.0 fundamentally reimagines Career Workflow from a simple CLI tool into a robust, AI-powered Job Operations Platform. 

#### Added
- **Runtime v2 Engine**: A fully decoupled orchestration engine using an internal `EventBus` and `Runtime State Manager`. Domain execution is now strictly separated from presentation.
- **Unified Runtime ViewModel**: A serializable projection of the active pipeline execution, pushed continuously to both the CLI and API.
- **Career Workflow Operations Center**: A 16-surface React application providing live telemetry, manual action queues, funnel conversion charts, and a queryable decision ledger interface.
- **Multi-Provider Inference Platform**: A cascading AI evaluation chain. Now defaults to **DeepSeek** (`deepseek-v4-flash`) for cost-effective reasoning, falling back seamlessly to local **OMLX** (`qwen3.5-4b`) upon network degradation.
- **Rich CLI**: A stunning terminal experience that renders `RunViewModel` state changes smoothly without console stutter.
- **Learning Platform & Cost Engine**: Real-time token usage telemetry and LLM cost analytics mapped across priority subtracks.

#### Changed
- Documentation has been structurally reorganized. The README acts as a product landing page while all technical depths have moved to a dedicated `docs/` architecture.
- The `Decision Ledger` schema has been hardened. Infinite application loops and duplicate execution are now cryptographically impossible.

#### Improved
- `cw doctor` now provides deep pre-flight health checks covering database locks, runtime snapshot statuses, and external API heartbeat checks.

---

## [3.0.0] - 2026-07-19

### Immutable Ledger & Provider Resilience

#### Added
- **Decision Ledger**: Migrated from simple CSV files to an authoritative SQLite database operating in WAL mode.
- **Search Cache**: Bypasses rate-limiting by caching acquisition queries. 
- **Challenge Cooldowns**: Safely isolates JobSpy execution blocks without halting the active run.

#### Changed
- Staged classification pipeline (Deduplicate → Hard Vetoes → Title Quality → AI Relevance → Detail Fetch).

---

## [2.0.0] - 2026-07-15

### Hybrid Questionnaire Resolution

#### Added
- Dual-engine resolution combining deterministic rules with LLM prompts to dynamically answer multi-page job application questionnaires.
- Candidate Evidence Profiles serving canonical answers to common screening questions.

---

## [1.0.0] - Initial Release

#### Added
- Initial Staged Pipeline Architecture.
- Naukri API direct integration.
- Standard Auto-Apply loops.