# Changelog

All notable changes to **Career Workflow** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [5.1.0] - 2026-08-15

### Grid Control Frontend Release (UI/UX)

This release is a **frontend/UI-only** release: the operations console was redesigned around the Grid Control / SCADA dispatch-room visual system. No backend, pipeline, provider, application-logic, or data-model behavior changed; all 24 routes, API contracts, and mutation semantics are preserved.

#### Added
- **Grid Control design system**: tokens (control-room continuum dark/light, semantic state hues, chart palette, fixed type scale), self-hosted fonts, terminal token, hairline surfaces with no drop shadows.
- **Control-room shell**: numbered navigation groups (01–06) covering all 24 routes, coordinate breadcrumb, truthful runtime status chip, mobile drawer, skip link, single command palette.
- **Shared operational primitives**: StateMarker (single status grammar — glyph + line form + label, hue only as confirmation), Panel/PanelHeader, PageHeader, StationTopology, EnvelopeTrace, GridSkeleton, EmptyState, ErrorState, Table grammar, toast channel.
- **Dispatch Overview**: station topology strip, operating-state (Process/Artifact/Portfolio), attention & faults, execution activity, key readings — all backed by real API data with honest idle/empty/error states.

#### Changed
- All 24 routes restyled to the Grid Control grammar (core operations, Copilot surfaces, Intelligence, telemetry, diagnostics).
- Status presentation unified: both incumbent badge systems now render through the single StateMarker grammar.
- Tables normalized (mono uppercase tracked headers, keyboard-accessible rows, consistent sortable/pagination/empty/error states).
- Loading/empty/error states standardized across every data surface; errors are visible and retryable, never silent.

#### Improved
- Accessibility: aria-labels on icon-only controls, keyboard-navigable rows/tabs/selects, focus restoration on sheet/dialog close, visible focus rings in both themes, heading hierarchy, skip link.
- Responsive: no horizontal overflow at 1440/1280/1024/768/375; mobile drawer with scrim/Escape/close-on-navigation; scrollable tabs/table wrappers on small screens.
- Reduced-motion support: all animation disabled under prefers-reduced-motion; polling causes no visual thrash.

#### Fixed
- Radix Sheet/Dialog Escape-close under React StrictMode (first Escape was swallowed; now deterministic force-close).
- Focus loss to `<body>` when conditional sheets closed (focus restored to the invoking row).
- Jobs table virtualization (all rows were rendered; now only visible + overscan rows, ~35 instead of 3963 in DOM).
- Page-level overflow at 375px on Jobs/Applications/Logs/Audit (toolbar wrapping, tablist/table horizontal scroll).
- Silent-error surfaces on 13 pages (providers, system, ledger, jobs, queues, explorer, metrics, logs, audit, config, developer, intelligence, runs).

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