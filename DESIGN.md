# DESIGN — Career Workflow Next

**Mode: Operate.** This is a replacement visual world for an existing, working product (redesign, not polish). Product truth lives in `PRODUCT.md` and in `README.md` (the product authority). Incumbent UI is evidence and anti-reference (`UI_AUDIT.md`). Companion docs: `UI_INVENTORY.md`, `UI_ROUTES.md`, `UI_COMPONENTS.md`.

> **DIRECTION: GRID CONTROL — SCADA / EMS DISPATCH ROOM. HUMAN-SELECTED (2026-08-15).**
> The operator explicitly chose this direction after a full Impeccable direction roll. It supersedes all earlier direction documentation, including the previous "Signal Desk" contract that this file once held. Signal Desk and every other candidate are **rejected** and retained only as historical exploration (§17). This file is the authoritative visual contract.

## 0. Identity independence (binding)

Career Workflow Next has an **independent visual identity**. It must not inherit, borrow, or echo the Pramya project's visual language, layout grammar, typography, colors, grid treatment, component styling, or aesthetic. It must also not converge on: a generic SaaS dashboard, a generic admin panel, a job-board clone, a Linear clone, a Notion clone, a generic AI dashboard, a glassmorphism template, a gradient-heavy AI landing page, or a cyberpunk/neon rendering of a control room. The identity below is derived from this product's own operating context (README.md §§1–10), not from any sibling project.

## 1. Visual thesis

Career Workflow is a **closed-loop AI job-operations control plane** — a dispatch/control system, not a dashboard of widgets. The UI must make **system topology, flow, state, capacity, faults, and decisions legible** the way a SCADA/EMS control room makes a power grid legible: the operator sees the whole system as a diagram, sees what is live, what is loaded, what is gated, what is degraded, and where the evidence points.

The system's real structure (README §5, §6.7) is: **Providers → Acquisition → Classification → Scoring → Policy/Diversity → Selection → Application Routing → Execution → Decision Ledger → Lifecycle/Analytics → evidence-driven strategy**, with a documented evidence-gated feedback loop. The interface renders *that* topology — never an invented one.

**Positioning statement:** observation surfaces read like the control-room wall (system truth at a glance); action surfaces read like the dispatch desk (deliberate, gated, confirmable). The console is ~70% observation / 30% action; the design honors that ratio in chrome weight, density, and interaction depth.

## 2. Visual identity

Unmistakably different from Pramya and from every rejected direction. Explicit non-negotiables:

- **No Pramya inheritance:** no Drawing Sheet, no drafting-grid treatment, no sheet metaphor, no engineering-drawing aesthetics, no drafting typography.
- **No paper/ledger-page aesthetic:** no ruled-book columns, no bookkeeping voice, no paper textures (this was "The Ledger" direction — rejected).
- **No emission-spectrum aesthetic:** no seven-wavelength legend, no spectral line set, no doubled sodium line, no wavelength tokens, no instrument-plate imitation (this was "Signal Desk" — rejected).
- **No cyberpunk/neon SCADA:** no glowing edges, no neon circuit lines, no sci-fi HUD. The control room is *restrained*, modern, and legible first.

The identity: a **calm, modern control room**. Dark = the dispatch environment (near-black, low-glare, cool neutral charcoal). Light = the designed **schematic print mode** — the same diagram on white, the way an engineering office prints a single-line diagram. Same symbols, same grammar, two faithful renditions of one world.

## 3. Control-room language

A restrained modern SCADA/EMS vocabulary. **Each term is a visual/interaction primitive AND a real data anchor** — a term is used only where the underlying backend actually provides the data. Where data is absent, the primitive renders an honest absent state (§10 of UI_AUDIT.md: no silent empties).

| Term | Real product anchor (README / API) | Rendered as |
|---|---|---|
| **Station** | A pipeline stage — preflight, acquisition, classification, selection, application, reconciliation, strategy, report (`latest_run.stages`, `timeline.json`, `/pipeline/state`) | Labeled unit on the topology conductor; per-stage state from run artifacts |
| **Feeder** | One provider's acquisition stream: Naukri API, JobSpy (Indeed / LinkedIn / Google) (`provider_health` in `/api/dashboard`; `/providers`) | Upstream feed lines entering the acquisition station; health from provider data |
| **Bus** | The aggregated flow conductor connecting stations (the documented pipeline spine) | One horizontal conductor in the topology strip; hairline, never decorative |
| **Node** | A job/application record moving through the pipeline (ledger rows, queue rows, jobs table) | Row/card carrying a state marker + score + lifecycle |
| **Breaker** | A gate that opens/closes flow: the policy chain of README §6.3 (min score → already-applied → company cap → role-family cap → run limit), challenge cooldown (§6.1), posting-age policy, dry-run isolation | Open/closed/tagged symbol on a flow segment; state derived from pipeline state, run artifacts, config |
| **Tag** | A hold: manual-review / external-apply / other-action queues, copilot answer locks, dry-run suppression, cooldown tags | Tag plate attached to a node or station; count + reason label |
| **Dispatch lane** | The application router's execution lanes — Naukri Native, ATS Handler, External Engine (README §5 "Application Execution Engines") — plus the manual-review lane (`applied_jobs.json`, `external_apply.json`, `manual_review.json`, queue endpoints) | Lane strip showing routed counts per lane |
| **Load trace** | Application throughput vs run limits and budget; provider query load vs cooldown (run counts, config ceilings, queue lengths) | Filled trace with operating-envelope bound |
| **State marker** | The single status glyph grammar (§4) | Symbol + line form + label; color only confirms |
| **Fault isolation** | Provider degraded → remaining queries for that site skipped (README §9: 3 consecutive failures → degraded); retry budget; terminal-state accounting | Isolated segment shown open + tagged, with the cause labeled |
| **Operating envelope** | Policy bounds: max applications per run, per-company cap, role-family cap, min score, posting-age threshold (config values, README §14) | Shaded bound region on load traces; config readout |

**Three kinds of truth** (README §8) map onto control-room records and stay visually distinct:
- **PROCESS STATE** = live telemetry (what the launcher/scheduler is doing now) — from `/api/runtime`, `/api/pipeline/state`.
- **ARTIFACT STATE** = the event recorder (what the latest immutable run artifact records) — from `/api/runs/*`, artifact endpoints.
- **PORTFOLIO STATE** = the historian (what the Decision Ledger records over time) — from `/api/ledger/*`, `/api/dashboard` lifecycle.

These three never share one visual treatment. Telemetry reads live (markers, traces, lamps), artifacts read recorded (timeline strips, manifest facts), ledger reads authoritative (rows, tables, totals).

## 4. Status grammar

**One semantic state system, product-supported states only.** Status is never communicated by color alone: every status is **symbol shape + line form + text label**, with hue as a confirming second channel. This satisfies WCAG AA and the audit's C1 (status-color chaos) with one grammar.

### Semantic states (each maps to real backend states)

| State | Product truth (backend supports) | Line form / glyph |
|---|---|---|
| **HEALTHY** | `system_health: HEALTHY`; provider healthy; run completed; lifecycle in good standing (Applied/Shortlisted/Interview) | Closed breaker, solid line, filled glyph |
| **RUNNING** | Scheduler `RUNNING`; `pipeline_running`; stage in progress; run active | Closed breaker, solid line, live glyph (pulses only while live) |
| **DEGRADED** | `system_health: WARNING`; provider `degraded`; partial results; recoverable failure | Half-open breaker, half-height line |
| **BLOCKED** | Policy gate opened (below min score, cap exceeded, duplicate, age-rejected); challenge cooldown active; dry-run suppressing live; lock held | Open breaker, dashed line |
| **PENDING** | Scheduled execution, upcoming run, scheduled stage, queued work | Open breaker, dotted line |
| **MANUAL-REVIEW** | manual-review / external-apply / other-action queues; unresolved questionnaire; opportunity needing action | Tagged breaker (tag plate attached) |
| **FAILED** | Recoverable failure, run failure, transition error, pipeline error | Faulted glyph (struck line), cause label |
| **TERMINAL** | Terminal failure accounting; terminal lifecycle (Rejected / Offer); archived runs | Closed-and-latched glyph (double-struck), recorded tone |

**Idle/absent:** scheduler `STOPPED`/`IDLE`, no run on record — rendered as an unlit bus with a neutral label. **Never** an always-green "Operational" pill (audit A7): health derives from `/api/runtime` + `/api/copilot/health` truthfully, with an explicit "unreachable" state on fetch failure.

**One primitive:** `StateMarker` renders every status above (glyph + line + label + optional hue). It replaces both incumbent StatusBadge systems (audit X1) and the shadcn badge. The lifecycle set (Acquired/Submitted/Viewed/Shortlisted/Interview/Rejected/Offer) and pipeline stage states map through the same marker grammar.

## 5. Topology

The real pipeline (README §5) becomes the visual spine. **No invented relationships** — every line drawn between components corresponds to a documented data flow.

- **The topology conductor:** stations in pipeline order on one bus, upstream **provider feeders** fanning into acquisition, downstream **dispatch lanes** (native / ATS / external) leaving the router, **Decision Ledger** as the sink, and the **evidence-driven strategy** loop drawn as a labeled return path (README §6.7 — real feedback, rendered as a labeled dashed return, never as decorative circuitry).
- **Live state per station:** each station carries a state marker from real run/pipeline data; an active run lights stations in sequence (dispatch progress).
- **Breakers on flow segments:** policy gates (README §6.3 chain), cooldowns, dry-run, and holds render as breaker symbols on the segments they gate — with the config value or reason labeled.
- **Where topology data is absent** (e.g., no active run), the conductor renders empty with an honest idle label; stations that have no data are dimmed, never invented.
- **Topology is a component, not a wallpaper:** `StationTopology` is used on Overview, Pipeline, Runs, and Explorer — everywhere pipeline state is inspected. It is not repeated decoratively elsewhere.

## 6. Dashboard composition (Overview)

The Overview is a **system-level dispatch view**, not a grid of metric cards. It composes five zones, in reading order, each from real data:

1. **Topology strip** — the pipeline conductor with live station state, provider-feeder health, and active-run progress (`/api/dashboard` `latest_run`, `system_health`, `provider_health`; `/api/runtime`).
2. **Operating state bar** — scheduler state, pipeline state, and the three kinds of truth (process / artifact / portfolio) each in its own labeled strip with truthful markers (`/api/runtime`; audit A7).
3. **Attention / fault conditions** — real items only: manual-review / external-apply / other-action queue counts, degraded providers, latest run failure. Honest quiet state when clear ("no attention items"), never fabricated rows.
4. **Execution activity** — latest run (id, mode, status, stages, counts) + recent lifecycle movement from the ledger. Honest idle state when no run is on record.
5. **Key readings** — a compact instrument row of the few numbers that matter (acquired, submitted, submit-success rate, routed, selected), rendered as labeled readings with load/envelope context — **not** a clickable-looking card grid (audit H4 dead affordance).

Loading = one structural skeleton; empty = one honest EmptyState; error = one ErrorState with refetch (audit F2/F3/F4).

## 7. Page composition (24 routes)

Route contracts, functionality, and data wiring are **preserved unchanged** (UI_ROUTES.md is the route authority). Pages share the Grid Control identity via the shared grammar; they never re-implement chrome.

Page types (each with a consistent internal rhythm):

- **Dispatch surfaces** — `/pipeline`, `/` (Overview): topology + breakers + launch controls. The only action-heavy surfaces.
- **Inspection surfaces** — `/runs`, `/explorer`, `/ledger`, `/logs`, `/audit`, `/system`, `/developer`: recorded truth; read-only; high density; artifact/event vocabulary.
- **Workspace surfaces** — `/jobs`, `/applications`, `/copilot/inbox`, `/copilot/apply/:id`, `/copilot/assistant/:sessionId`, `/copilot/brief/:id`: row-level operations; dispatch-lane and tag vocabulary; the copilot wizard keeps its 5-step semantics (brief → answers → resume → assistant → submit).
- **Intelligence surfaces** — `/metrics`, `/intelligence`, `/copilot/analytics`, `/copilot/history`, `/copilot/learning`: traces, tables, funnel; the "historian" register.
- **Configuration surfaces** — `/configuration`, `/copilot/settings`, `/providers`, `/about`: envelopes, config readouts, provider health.

Shared chrome rules: one page header (index + title + actions), one panel, one state-marker grammar, one table grammar (TanStack primitives everywhere; Ledger migrates from raw `<table>` — audit X2), one tab grammar (rebuilt `ui/tabs` replaces custom bars + the Pipeline segmented toggle becomes a radiogroup-style ToggleGroup — audit A3/X4), one toast channel (sonner, already a dependency — audit F1), one EmptyState, one ErrorState (audit F3/F4), one command palette (delete the duplicate — audit X3).

## 8. Data visualization

Only where backed by real data:

- **Topology diagrams** — the real pipeline (§5), per-station real state.
- **Load/capacity traces** — throughput vs run limit / budget; provider load vs cooldown. Envelope bound drawn from config ceilings; series from run/queue counts.
- **Stage progression** — per-run stage timeline from `latest_run.stages` / `timeline.json`: stations lit in sequence with stage durations.
- **Event/state timelines** — ledger status events, run timelines, copilot sessions: one timeline primitive (ticks on a conductor, current position marked).
- **Operational tables** — jobs, ledger, queues, applications: one table grammar (TanStack), `SortableHeader` with `aria-sort` (audit A4), keyboard row activation (audit A5), sticky-first-column + horizontal scroll instead of truncation (audit R2).
- **Ledger views** — ledger search/stats with decision, score, and audit-trail columns; the sheet detail keeps AI-analysis, event timeline, and raw JSON (restyled, one terminal token — audit C4).

Chart rules: Recharts retained; all series colors from the token set (fix audit C5 — `--chart-1..5` become real tokens); hairline grids at emphasized ticks; mono axis labels; tooltips as flat hairline panels; no gradients, no 3D, no gauge chrome (a gauge is only drawn when it reads a real number).

## 9. Interaction

**Observation dominates.** Inspection surfaces are read-only with minimal chrome; their density and legibility are the design priority.

**Operator actions stay deliberately gated** (behavior unchanged — the backend contract is frozen):

- Pipeline launch: dry-run default; live requires the existing ConfirmDialog + the confirm-token semantics preserved (`--confirm-live` affordance stays explicit in the UI).
- Destructive/live operations: gated behind confirm, clearly labeled LIVE vs DRY, with a running indicator while in flight.
- Queue transitions, copilot answer locks, and browser actions: keep their existing direct `fetchApi` behavior; all get toast feedback (audit F1) — no optimistic updates until the backend supports idempotent replay (out of scope; contract frozen).
- Breakers and tags are clickable *only where a real backend action exists* (e.g., opening a held queue item, releasing a dry-run hold). A breaker with no action renders as a static state, never as a dead affordance (audit H4 rule: no fake clickability).

Interaction states: focus = visible ring on every interactive element (audit AX2); hover = surface step + border strength, never color-only; disabled = struck/tagged forms; touch targets ≥ 36px.

## 10. Responsive

| Width | Behavior |
|---|---|
| **1440** | Full dispatch board: topology strip at full width, side panels for attention + readings, tables at full density |
| **1024** | Rail condenses (icon rail); panels stack to one column; topology strip stays horizontal but panels move below |
| **768** | Drawer navigation (rail → off-canvas with scrim); topology reflows to a vertical station flow; tables scroll horizontally with sticky first column; fixed heights become viewport-flexible (audit R3) |
| **375** | Single column; drawer nav; vertical topology; dispatch lanes stack; key action controls stay reachable; touch targets ≥ 36px |

No mobile nav breakage (audit R1): the rail becomes a drawer below `lg`; ⌘K persists; breadcrumb becomes coordinates.

## 11. Dark + light

- **Dark (default):** the dispatch environment — near-black cool charcoal ground, low glare, hairline separations, restrained single-accent operational colors. The operator's physical scene: one person, dim room, screen-lit, late-night and early-morning sessions.
- **Light:** the **schematic print mode** — a designed white diagram ground with the same symbols, line grammar, and markers, printed with higher ink contrast. It is a faithful second rendition of the same control room (the way SCADA prints to white), **not an inverted dark theme** (audit C2) and **not** a paper/ledger-page aesthetic (§2). Both themes pass AA contrast at every type size.

## 12. Motion

Only operationally meaningful motion. A closed set:

1. **State transition snap** — breaker/station state changes flip crisply (150–200ms, no bounce).
2. **Live trace** — load/activity traces advance while live; running markers pulse only while live.
3. **Dispatch progress** — an active run lights stations in sequence along the topology (the one authored moment).
4. **Fault/change indication** — a new fault/change flashes once and **persists as a labeled marker until acknowledged** (unacknowledged-alarm principle), with text, never hue-only.

`prefers-reduced-motion`: all motion off; states remain distinct via line form and labels. No decorative animation, no entrance staggers on data (5s polls must not re-animate), no parallax, no infinite spinners.

## 13. Accessibility

- WCAG 2.1 AA in both themes; status never hue-only (symbol + line + label, §4).
- Skip-link to `#main-content` (audit AX4); `aria-current` on active nav; `aria-live="polite"` on polling regions (log, metrics, attention panel — audit AX3).
- Keyboard: full shell navigation (rail + drawer), Enter/Space row activation (audit A5), radiogroup semantics on the dry/live toggle (audit A3), `aria-sort` on sortable headers (audit A4), arrow-key tabs, preserved ⌘K + inbox j/k.
- `aria-label` on every icon-only control (audit A2); focus-visible rings on custom controls (audit AX2).
- Dialog/sheet focus traps via existing Radix primitives; reduced-motion honored.

## 14. Anti-patterns (explicit prohibitions)

- Cyberpunk neon, glowing sci-fi dashboards, HUD effects, neon circuit lines.
- Fake network topology: nodes/lines/links with no backend data behind them (the topology is §5's real pipeline only).
- Decorative circuit traces, "signal" squiggles, ornamental schematics.
- Excessive status colors, alarm-wall red (unbounded simultaneous red), rainbow status legend.
- Card-grid SaaS layouts, decorative card grids, generic admin panels, job-board clones, Linear/Notion clones, generic AI dashboards.
- Glassmorphism / backdrop-blur surfaces, gradients (any), drop shadows (elevation = surface step + hairline + scrim only).
- Gratuitous gauges: circular dials/knobs that read no real number.
- Fake telemetry, invented metrics, decorative readouts (every number traces to an endpoint or config).
- Aviation / photography / ledger metaphors: boarding passes, gate boards, darkrooms, film, double-entry bookkeeping.
- Signal Desk language: spectral legend, wavelength tokens, doubled sodium line, instrument-plate imitation.
- Pramya / Drawing Sheet inheritance: drafting grid, sheet metaphor, engineering-drawing aesthetic.
- Emoji, mascots, illustration, decorative photography, ornamental icons.
- Per-page dialects: one badge, one card, one table, one loading idiom, one empty state, one error state (the audit's core failure mode).

## 15. Signature elements (survive all 24 pages, never decoration)

1. **The Station Topology Strip** — the real pipeline as stations on one conductor with live breakers and dispatch progress. Appears on Overview, Pipeline, Runs, Explorer; on every other page a compact one-line conductor sits in the page header, keeping the system in view without decoration.
2. **The Breaker/State glyph grammar** — open/closed/tagged breaker symbols + state markers (§4). Every status in the app speaks this one vocabulary.
3. **Dispatch Lane strips** — the router's execution lanes (native / ATS / external) plus the manual-review lane, shown as labeled lane counts wherever routing/queues appear (Overview attention, Applications, Inbox).
4. **The Envelope/Load readout** — capacity vs budget as a filled trace with a labeled operating-envelope bound (Overview readings, Pipeline ceiling, Metrics).

## 16. Redesign order

1. **Design tokens** — rewrite `index.css` (control-room continuum, breaker/state token set, real `--chart-1..5`, spacing/radius scales, terminal token — fixes C4/C5/D1), `tailwind.config.js` (map state + chart + type-scale tokens), self-host fonts (kills the Google `@import` first-paint block — audit T1), delete `App.css` duplicate scrollbar + `shadow-card` no-op.
2. **Shell / navigation** — rail with group indices, coordinate breadcrumb, truthful runtime status (audit A7), mobile drawer (audit R1), skip link, single command palette.
3. **Shared primitives** — StateMarker (kills both badge systems — X1), Panel/PanelHeader (kills the 12-file card idiom), Button, Table grammar (X2), Tabs/ToggleGroup (X4/A3), Select/Input/Label (A1), Skeleton, EmptyState, ErrorState, Toast (F1), Timeline, StationTopology, Envelope/load trace, ConfirmDialog restyle.
4. **Overview representative implementation** — the dispatch view (§6) establishes the language end-to-end; becomes the visual validation target.
5. **Visual validation** — batched screenshot round (desktop + mobile, dark + light) + `npm run gate` (typecheck/lint/build) green; one fix batch max.
6. **Remaining pages**, in dependency order: Ledger (table + sheet) → Jobs (virtualized table) → Pipeline (dispatch + gating) → copilot wizard (Apply, Assistant, Brief, Inbox) → Intelligence/Metrics → Runs/Explorer → Applications/History/Learning → System/Providers/Logs/Audit/Developer/Configuration/Settings/About.
7. **Responsive pass** — drawer, sticky columns, viewport-flexible heights, touch targets (§10).
8. **Accessibility pass** — every audit AX/A item (§13).
9. **Motion pass** — the §12 closed set + reduced-motion.
10. **Final audit** — Impeccable mechanical detector + finish review; then the shipped documenter records the system; cleanup dead files (CommandMenu duplicate, CopilotPlaceholder, keyword StatusBadge).

**Known frontend-test gap (pre-existing, not fixed here):** the only frontend test (`src/__tests__/sort.test.ts`) targets vitest, but vitest is not in `package.json` and there is no test script; adding the dependency is out of scope (backend suite: 524 passing). Validation uses `tsc -b` + `build` + `oxlint` + the screenshot/overflow matrix.

## 17. Rejected directions (historical exploration only)

Both Impeccable direction rolls are recorded here for history. **None of these is selected; none may be revived as the world.** Grid Control was chosen by the operator.

### Roll 1 (discovery pass, 2026-08-15) — previously documented as "Signal Desk"

Assigned: generative parametric identity. Challengers: orizuru fold-sequence, tensegrity breathing column, stitched-leather studio, **emission-line spectrograph rail**, film cutting bench.

| Direction | Verdict (roll 1) | Status now |
|---|---|---|
| Emission-line spectrograph ("Signal Desk") | Won roll 1; previously documented in this file | **Rejected** — superseded by human selection; its aesthetic (spectral legend, wavelength tokens) is explicitly banned (§2, §14) |
| Generative parametric identity | Competitive alternate | Rejected |
| Film cutting bench | Competitive alternate | Rejected |
| Tensegrity column | Declined (donated constraint-state idea) | Rejected |
| Orizuru folds | Declined (donated step-state idea) | Rejected |
| Leather studio | Declined | Rejected |

### Roll 2 (direction exploration, 2026-08-15, seed key `fb42c0bb`)

Challengers dealt: printing darkroom safelight bay, HyperCard shoebox stack, theater cyclorama dawn, cloud quarry, dark-first developer console, boarding-pass + gate board. Grounded candidates authored from the operator's cultural world (mission control, double-entry ledger, gate boards, instrument benches, CI/CD boards, SCADA/grid dispatch, field notebooks).

| Direction | Axis read (audience id / product clarity) | Status now |
|---|---|---|
| **Grid Control — SCADA dispatch room** | Strong / medium-strong | **HUMAN-SELECTED → the build direction** |
| Safelight Darkroom | Medium-strong / strong | Rejected (boldest alternate) |
| The Gate Board | Strong / strong | Rejected |
| The Ledger (double-entry) | Strong / strong | Rejected |
| Cyclorama | Competitive on boldness / weak clarity | Rejected |
| Cloud Quarry | Low audience id | Rejected |
| HyperCard | Seductive one-bit / conflicts with status legibility | Rejected |
| Developer Console | Strong clarity / weakest identity | Rejected |

**Selection rationale (operator, verbatim intent):** Grid Control represents the actual system topology — provider health/degradation, pipeline stages, runtime monitoring, application routing, run limits, policy/diversity controls, Decision Ledger, Pipeline Explorer, System Health, Runtime, Analytics, scheduler/recovery — rather than decorating the product with an unrelated metaphor.

---

## Appendix A — Carried factual findings

- **Audit standing:** P0 none; P1×11 (T1, C1, C2, A1, A2, A6-partial, F1, F2-partial, R1, X1, X2); P2×21; P3×12 — full register in `UI_AUDIT.md` (unchanged; referenced by code above).
- **Terminology preserved:** Decision Ledger, run artifacts, dry-run vs live, pipeline stages (preflight, acquisition, classification, selection, application, reconciliation, strategy, report), lifecycle stages (Acquired/Submitted/Viewed/Shortlisted/Interview/Rejected/Offer), manual-review/external-apply/other-action queues, copilot workspace.
- **Stack (UI_INVENTORY.md, unchanged):** React 19.2 / Vite 8 / TS ~6 / Tailwind 3.4 (class dark) / shadcn `ui/*` 16 primitives (4 dead: label, select, skeleton, tabs) / TanStack Query + Table + Virtual / Recharts 3.9 / Zustand 3 stores / lucide / date-fns; declared-but-unused: sonner, framer-motion, react-hook-form, zod.
- **Data layer:** single `fetchApi` (relative `/api`, 90s timeout, 3-envelope error parsing); ~30 `useQuery` hooks, polling 1s–30s; mutations only in Pipeline (`launchPipeline`); queue/copilot writes direct `fetchApi`, no invalidation.
- **Backend contract:** frozen; UI is a pure consumer; `system_health` returns HEALTHY/WARNING with `scheduler_running`/`pipeline_running`; `/api/runtime` returns scheduler RUNNING/IDLE/STOPPED/STALE/ORPHANED + pipeline + latest_run_details; queue endpoints return `{items}`; `upcoming_executions` is a backend placeholder returning `[]` — the UI renders honest idle, never invented entries.
