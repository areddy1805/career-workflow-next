# UI Audit — Career Workflow Next (current interface)

Audit conducted 2026-08-15 against source (`frontend/src`), Impeccable Operate-mode vocabulary. This pass classifies only; fixes are scoped to the redesign (DESIGN.md). Evidence = file:line or file-level grep counts.

## Verdict summary

The app has a **de-facto style** (hairline cards, 10px uppercase labels, mono numerics, no shadows, 6px radius, dark-first) but **not a design system**: it is a consistent-looking collection of hand-rolled idioms with two parallel badge systems, four loading idioms, three empty-state languages, ~380 hardcoded status colors, and 4 dead primitives. It reads as a competent engineer's UI that converged on "dark admin" by habit. The strongest asset is the operations kit (`operations/*`) — the redesign formalizes what that kit accidentally started.

Classification: P0 broken · P1 major UX · P2 significant design · P3 polish.

---

## Hierarchy

| # | Sev | Finding | Evidence |
|---|---|---|---|
| H1 | P2 | Page hierarchy is flat: nearly every label is 10–13px uppercase with tracking; only SectionTitle (text-lg) separates page from section. No type hierarchy above 18px anywhere. | `operations/SectionTitle.tsx` (h2 text-lg); 10px uppercase headers across Pipeline/Dashboard/Ledger |
| H2 | P2 | Three chrome layers (sidebar 240px, topbar 48px, main padding 24–32px) + `max-w-7xl` create a shallow, centered composition; dense pages (Ledger) feel identical in weight to thin pages (Configuration 71 lines) — no page-type differentiation (observation vs action vs config). | App.tsx Layout |
| H3 | P3 | `SectionTitle` action slot is used as a badge/summary dump on Ledger (two stacked stat columns) — action slot ≠ data slot. | Ledger.tsx SectionTitle action |
| H4 | P2 | Dead affordance: MetricCards render `cursor-pointer hover:border-foreground/30` with no onClick handler. | Dashboard.tsx MetricCard className |

## Typography

| # | Sev | Finding | Evidence |
|---|---|---|---|
| T1 | P1 | **Fonts load from Google Fonts via CSS `@import`** — first paint blocks on network; offline dev = fallback font shift. No self-hosting, no `font-display: swap` control. | index.css:1 |
| T2 | P2 | `letter-spacing: -0.015em` globally with line-height 1.6 and 10–13px labels — tight-tracking tiny text at high volume is legibility risk; comment admits "Extremely tight for premium feel" (intent, not evidence). | index.css body |
| T3 | P3 | Metric values use `font-mono` (JetBrains) — strong instrument feel, but mono values mixed with Inter numerals without tabular alignment in tables (Score column uses `tabular-nums` only on Jobs). | MetricCard.tsx; Jobs.tsx score cell |
| T4 | P3 | No type scale: 9px/10px/11px/12px/13px/text-sm/text-lg all coexist; many are literal classes (`text-[9px]`, `text-[11px]`) rather than scale tokens. | grep `text-[1-9]` across src |
| T5 | P2 | Uppercase-everything tendency: labels, buttons, badges, telemetry keys, group headers — ~60+ `uppercase tracking-*` instances. Caps are the default voice, not an accent. | grep count |

## Contrast & color

| # | Sev | Finding | Evidence |
|---|---|---|---|
| C1 | P1 | **Status color chaos**: ~380 hardcoded `emerald/amber/red/blue/purple/zinc` class usages while the CSS defines `--success/--warning/--error/--info` tokens that are NEVER consumed (not even mapped in tailwind.config). Two parallel badge systems encode status twice. Semantic status is not centralized — impossible to re-theme consistently. | grep (audit 2026-08-15); index.css `--success` etc.; tailwind.config.js (no success/warning/info entries) |
| C2 | P1 | Light theme is visually unmaintained: tokens exist (`.dark` override + light `:root`), toggle exists, but the entire app's QA has been dark; light-mode contrast for `--muted-foreground` (45% on white) and 10px text fails AA at these sizes. | index.css `:root`; Preferences store default dark |
| C3 | P2 | Status greens/blues are used interchangeably for "running" (emerald dot in Topbar, blue chip in PipelineTracker, cyan nowhere) — the same semantic (in-flight) has 3 hues. | App.tsx Topbar emerald; Dashboard PipelineTracker blue |
| C4 | P2 | Hardcoded terminal backgrounds: `#0a0a0a` ×4 and `#0d1117` ×1 — two different near-blacks for the same concept (log/JSON terminal), neither tokenized. | Pipeline.tsx:93, Ledger.tsx:287, ErrorBoundary.tsx:36,59, Logs.tsx:71 |
| C5 | P2 | `chart-1..5` referenced in tailwind config but never defined — chart theming is effectively absent; series colors live inline in Recharts props (Metrics LIFECYCLE_COLORS hex map). | tailwind.config.js; Metrics.tsx:31 |

## Density, spacing, alignment

| # | Sev | Finding | Evidence |
|---|---|---|---|
| D1 | P2 | Density is genuinely high (good for this product) but uncontrolled: 4px/8px/12px/16px paddings chosen per-card; no spacing scale discipline (gaps of 0.5/1/1.5/2/3/4/5/6 all used). Compact vs comfortable density setting exists but is **unused** (no consumer of `density` in src). | preferences.ts density; grep |
| D2 | P3 | `gap-px bg-border/50` telemetry grid trick (Pipeline) — clever but brittle; a hairline-grid utility would be one grammar. | Pipeline.tsx Telemetry |
| D3 | P3 | Card headers inconsistent: `px-4 py-3` vs `px-4 py-3.5`, `border-b border-border/50` vs `/40` vs `/60`; 3 border-opacity dialects. | Dashboard/Pipeline/Ledger headers |
| D4 | P3 | Alignment drift in table cells: font sizes 10/11/12/13px mixed within one table (Ledger). | Ledger.tsx cells |

## Affordances & interaction states

| # | Sev | Finding | Evidence |
|---|---|---|---|
| A1 | P1 | **Raw `<select>`s** in Ledger + copilot/Inbox: native select with custom class, inconsistent with the rest of form styling; keyboard UX fine but visual affordance weak; ui/select (accessible, styled) is dead. | Ledger.tsx, copilot/Inbox.tsx, UI_COMPONENTS dead-list |
| A2 | P1 | Icon-only actions frequently lack `aria-label`: ~23 button candidates without one (estimate); several rely on `title` only. | grep `<button` audit |
| A3 | P2 | Custom segmented toggle (Pipeline Dry/Live) is two `<button>`s styled as a switch — no radiogroup/tablist semantics, no arrow-key nav. | Pipeline.tsx mode toggle |
| A4 | P2 | SortableHeader is a clickable `<th>` (div inside th) without `aria-sort`/`button` semantics; three-click sort state (asc/desc/none) is invisible until clicked. | SortableHeader.tsx |
| A5 | P2 | Ledger rows are click targets (open sheet) with no affordance beyond hover bg; keyboard selection absent (row click only, no Enter/Space). | Ledger.tsx tbody |
| A6 | P2 | Context-menu-only actions in Jobs (row right-click) are invisible and not discoverable on touch — primary row actions should exist as visible controls too. | Jobs.tsx |
| A7 | P3 | Topbar "Operational" live pill is always green (emerald + pulse) regardless of actual state — a decorative status claim. | App.tsx Topbar; useCopilotHealthBadge not consulted here |

## Feedback & state communication

| # | Sev | Finding | Evidence |
|---|---|---|---|
| F1 | P1 | **No toast/notification channel**: launch, queue transitions, answer locks, copy actions have no transient success/error feedback (only inline states that some pages omit entirely). Sonner already a dependency, unused. | grep sonner = 0 |
| F2 | P1 | Loading: 4 idioms (skeleton blocks / overlay pill / pulse text / row spinner) with no shared primitive; overlay pill (Ledger) covers the table with backdrop-blur — visually heavy for a 15s poll. | Dashboard skeleton; Ledger overlay; Pipeline pulse; Jobs spinner |
| F3 | P2 | Empty states: 3 dialects (dashed border, icon+2line, plain text) — no EmptyState component; empty search results in copilot Inbox vs Ledger differ in tone. | Dashboard funnel, Ledger, Jobs |
| F4 | P2 | Error states: inline red text only in Pipeline; Dashboard/Runs/Metrics silently render empty on query failure (no error surfaced). | Pipeline.tsx error; Dashboard has no error branch |
| F5 | P3 | Optimistic updates: none; queue mutations + copilot answer edits don't invalidate queries → stale UI until poll. | Jobs.tsx transition (direct fetchApi) |

## Responsive

| # | Sev | Finding | Evidence |
|---|---|---|---|
| R1 | P1 | **No mobile navigation**: fixed 240px sidebar at all widths; on <768px the shell is 240px sidebar + squeezed content — effectively broken. No drawer, no bottom nav. | App.tsx Sidebar |
| R2 | P2 | Ledger table truncates via max-w on cells with no horizontal scroll container — data loss on narrow widths. | Ledger.tsx cells |
| R3 | P2 | Fixed heights: Pipeline log `h-[520px]`, funnel `h-[240px]` — not viewport-aware; on short screens content scrolls inside 3 nested scroll containers. | Pipeline.tsx, Dashboard.tsx |
| R4 | P3 | Touch targets: many controls 24–32px (badges, kbd, sort icons, chevrons) — below 44px guidance. | various |

## Accessibility

| # | Sev | Finding | Evidence |
|---|---|---|---|
| AX1 | P1 | See A2 (aria-labels), A3 (toggle semantics), A4 (aria-sort), A5 (row keyboard access), R1 (nav) — collectively the shell/table/toggle layers are not keyboard- or AT-complete. | — |
| AX2 | P2 | Focus-visible: shadcn primitives carry rings, but custom elements (segmented toggle, SortableHeader th, raw selects, clickable rows) define no focus style. | Pipeline toggle, SortableHeader |
| AX3 | P2 | `aria-live` absent: polling regions (log, dashboard metrics) update without announcing; toggles (sidebar collapse) don't announce state. | App.tsx, Pipeline log |
| AX4 | P3 | `id="main-content"` exists but no skip-link to it. | App.tsx |

## Motion

| # | Sev | Finding | Evidence |
|---|---|---|---|
| M1 | P2 | Motion is minimal and inconsistent: 18 `animate-in fade-in` page entries, `animate-pulse` skeletons, `pulse-green` dot — no transition grammar; framer-motion installed but unused (0 imports). Sidebar collapse animates 200ms but nav items don't stagger. | grep animate-in=18; framer-motion=0 |
| M2 | P3 | `pulse-green` is a manual keyframe duplicating Tailwind `animate-pulse` semantics — one pulse system should exist. | index.css |

## Consistency

| # | Sev | Finding | Evidence |
|---|---|---|---|
| X1 | P1 | **Two StatusBadge systems** (keyword-map 90 lines vs generic 37 lines) with different props; 15 pages pick one arbitrarily. | components/StatusBadge.tsx vs operations/StatusBadge.tsx |
| X2 | P1 | Two table grammars (TanStack virtualized in Jobs vs raw `<table>` in Ledger/Applications/Inbox/History) — different header styles, density, hover, selection. | Jobs.tsx vs Ledger.tsx |
| X3 | P2 | Two command-palette implementations (App.tsx inline vs components/CommandMenu.tsx unused) — drift risk. | App.tsx, components/CommandMenu.tsx |
| X4 | P2 | Custom tabs (Applications, Logs) vs unused ui/tabs — three tab renderings if counted. | Applications.tsx TABS, Logs.tsx |
| X5 | P2 | Page headers: SectionTitle (shared) vs inline header rows (Jobs, Inbox, copilot pages) — two header idioms. | Jobs.tsx, copilot/Inbox.tsx |
| X6 | P3 | Provider identity duplicated in two maps (Intelligence PROVIDER_META vs Providers PROVIDER_ICONS/COLORS) + provider color values differ between them. | Intelligence.tsx:15, Providers.tsx:9 |
| X7 | P3 | `any` typing pervasive in pages (Dashboard `latestRun: any`, Ledger items `any`, Jobs column cells `any`) — type debt that already caused schema drift (API contract normalization `_ensure_api_contract` in api/routes.py suggests prior breakage). | Dashboard.tsx, Ledger.tsx, api/routes.py:80 |

## AI/slop pattern register

- Gradient usage: absent (good). Glassmorphism: backdrop-blur only on topbar + Ledger overlay (restrained). Decorative icons: mostly absent — icons are functional.
- Slop tells present: 10px-uppercase-everywhere (uniform density = "designed by one tool"), dead affordances (cursor-pointer without action), decorative "Operational" pill always green, two near-identical badge systems, `#0a0a0a` vs `#0d1117` terminal blacks, shadow-card that literally disables shadows (a no-op utility masking intent), "Extremely tight for premium feel" comment (design-by-adjective), and the custom `Briefcase` SVG shadowing a lucide import.
- **Assessment**: the interface is competent and functional — a strong foundation to redesign from, not a disaster to escape. The work is formalization (tokens, primitives, one-of-each), hierarchy (page types, type scale), state language (status/loading/empty/error), and the missing channels (toast, a11y, responsive shell).

## Priority summary

- **P0**: none found (nothing visibly broken at runtime on the main flows in dark mode; no crashes observed in smoke run 2026-08-15).
- **P1 (11)**: T1, C1, C2, A1, A2, A6 (partial), F1, F2 (partial), R1, X1, X2.
- **P2 (21)**: H1, H2, H4, T2, T5, C3, C4, C5, D1, A3, A4, A5, F3, F4, F5, R2, R3, AX2, AX3, M1, X3, X4, X5.
- **P3 (12)**: H3, T3, T4, D2, D3, D4, A7, R4, AX4, M2, X6, X7.
