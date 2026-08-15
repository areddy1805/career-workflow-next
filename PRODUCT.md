# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Single operator: a software engineer running **their own** AI-powered job-search automation on a personal workstation. The console is used daily during an active job search, in bursts (morning triage, post-run inspection, evening review). High trust in numbers, low tolerance for hidden state. The operator is technical: comfortable with run IDs, JSON artifacts, terminal logs, and keyboard shortcuts. Inferred from the repo brief and operating context (local-only, personal automation, terminal-derived culture in the existing UI).

## Product Purpose

Career Workflow Next is a personal job-application operations platform: it discovers jobs across providers, evaluates them against a candidate profile with LLM-assisted scoring, applies policy-controlled application execution, and tracks every decision and lifecycle event in a persistent Decision Ledger. The console exists so the operator can launch, observe, audit, and intervene in this automation from one surface instead of terminal commands.

## Positioning

A **closed-loop, evidence-gated automation platform**: no blind auto-apply. Every stage (acquisition → classification → selection → application → reconciliation → strategy) is policy-controlled, and every outcome feeds back into adaptive strategy. The Decision Ledger (SQLite WAL) is the single source of truth, not the UI. The interface's job is operational truthfulness: showing process state, artifact state, and portfolio state as distinct things.

## Operating Context

- Local development machine; FastAPI backend (port 8090 dev) + React/Vite frontend (port 5173 dev), proxied `/api`.
- Operator works primarily in a dark environment (existing UI is dark-default, light mode exists but unused in practice).
- Pipeline runs are heavy: polling telemetry (1s–30s intervals), live log streams, run artifacts, 50+ record ledger pages.
- Destructive operations exist (live application runs) and are protected by explicit confirm dialogs and dry-run default.
- Copilot workspace: browser-assisted application flow with a 5-step wizard (brief → answers → resume → assistant → submit) and session state.

## Capabilities and Constraints

- 24 frontend routes across: Operations Center (overview, pipeline control, runs), Workflows (jobs, applications), Copilot (inbox, apply wizard, brief, assistant, history, analytics, learning, settings), Intelligence (ledger, insights, explorer), Telemetry (metrics, providers), Diagnostics (system health, logs, developer, audit).
- React 19 + Vite 8 + TypeScript ~6 + Tailwind 3 (class dark mode) + shadcn-style ui/ primitives + TanStack Query/Table/Virtual + Recharts + Zustand + lucide-react + date-fns. react-hook-form + zod + framer-motion + sonner are declared in package.json but NOT used in src (verified 2026-08-15).
- Backend contract must not change in this redesign: all data flows through existing `/api/*` endpoints; the UI is a pure consumer.
- Constraint: single operator, personal automation, local-first; no multi-tenant auth UI needed.
- Terminology that must be preserved: Decision Ledger, run artifacts, dry-run vs live, pipeline stages (preflight, acquisition, classification, selection, application, reconciliation, strategy, report), lifecycle stages (Acquired/Submitted/Viewed/Shortlisted/Interview/Rejected/Offer), manual-review/external-apply/other-action queues, copilot workspace.

## Brand Commitments

- Product name: Career Workflow (Next). Console logo wordmark currently "CareerFlow" (App.tsx) — resolves to Career Workflow at redesign.
- Explicit visual independence: **must not** inherit Pramya's visual language, layout grammar, typography, colors, grid treatment, component styling, or aesthetic.
- Explicit exclusions: no generic SaaS dashboard, no generic admin panel, no job-board clone, no Linear clone, no Notion clone, no generic AI dashboard, no glassmorphism template, no gradient-heavy AI landing page.
- The identity must communicate: intelligence, operational control, decision support, automation, job intelligence, pipeline state, evidence, application operations, analytics, confidence, actionability. "Wow" comes from hierarchy, composition, typography, information architecture, data presentation, clear states, purposeful interaction — not decoration.

## Evidence on Hand

- Real ledger and artifact data under `data/` and `artifacts/runs/` (real job records, run manifests, rejected/applied job lists).
- Screenshots in `assets/` (screenshot_overview.png etc.) documenting the incumbent console.
- `docs/` architecture documentation (ARCHITECTURE.md, OperationsCenter.md, application_copilot/*) — product truth, not design truth.
- 524 passing backend tests; frontend `gate` script (typecheck + lint + build).
- Incumbent UI is the primary anti-reference for the redesign (see UI_AUDIT.md).

## Product Principles

1. **Operational truth over decoration** — the console must make automation state legible at a glance; style never obscures state.
2. **Evidence before action** — scoring, decisions, and strategy changes are shown with their supporting evidence; the UI surfaces why, not just what.
3. **State semantics stay distinct** — process state, artifact state, and portfolio/ledger state are different kinds of truth and must not be visually conflated.
4. **Safety rails are visible** — dry-run vs live, confirmation of destructive actions, and running-state indicators are primary UI signals, never afterthoughts.
5. **Density with clarity** — the operator works with high-volume tabular data; density is a feature, legibility is the discipline that keeps it usable.
6. **Keyboard-first fluency** — navigation, command palette, and row actions should be reachable without the mouse (incumbent already has ⌘K, j/k inbox nav; preserve and extend).

## Accessibility & Inclusion

No product-specific user requirements beyond: full keyboard operability (existing ⌘K + j/k patterns), WCAG 2.1 AA contrast in both themes, focus-visible indicators, semantic landmarks/nav labels, and screen-reader labels on icon-only controls. Dark and light themes must both be first-class (light currently exists but is visually unmaintained).
