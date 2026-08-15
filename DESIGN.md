# DESIGN — Career Workflow Next

**Mode: Operate.** This is a replacement visual world for an existing, working product (redesign, not polish). Product truth lives in `PRODUCT.md`; incumbent UI is evidence and anti-reference (`UI_AUDIT.md`). Companion docs: `UI_INVENTORY.md`, `UI_ROUTES.md`, `UI_COMPONENTS.md`.

## 0. Identity independence (binding)

Career Workflow Next has an **independent visual identity**. It must not inherit, borrow, or echo the Pramya project's visual language, layout grammar, typography, colors, grid treatment, component styling, or aesthetic. It must also not converge on: a generic SaaS dashboard, a generic admin panel, a job-board clone, a Linear clone, a Notion clone, a generic AI dashboard, a glassmorphism template, or a gradient-heavy AI landing page. The identity below was derived from this product's own operating context (see `PRODUCT.md`), not from any sibling project.

---

## 1. Design principles

1. **Operational truth over decoration.** Every visual decision must make automation state more legible. If a style choice cannot be justified by legibility, it is not made.
2. **State is line, not hue.** Status semantics are encoded in line form and line weight first (solid = live, dashed = pending, half-height = stale, doubled = outranks); spectral hue is the second channel, never the only one.
3. **One way to express each structure.** One badge, one card, one table, one loading idiom, one empty state, one error state. Pages compose; they never re-implement chrome.
4. **Density is a feature; legibility is the discipline.** The operator works with high-volume tabular data. 10px mono labels are an accent for data, not the default voice for controls.
5. **Stable state language.** A daily-use console must be learnable once and stay stable. Nothing about the interface may mutate per-run, per-refresh, or per-data-state (see §9, "no parametric identity drift").
6. **Safety rails are visible.** Dry-run vs live, destructive confirmation, running indicators: primary UI signals, never afterthoughts.
7. **Two themes, both first-class.** Dark is the default operating environment; light must be designed, not inherited.

---

## 2. Visual direction — selection

Per the design-direction process (Impeccable new-work), a direction roll assigned **generative parametric identity** (a seed-derived, self-recomputing brand system) and dealt challengers: orizuru fold-sequence, tensegrity breathing column, stitched-leather studio, **emission-line spectrograph rail**, film cutting bench, and the seeded-identity system itself. Verdicts, on exactly two axes — **audience identification** (does the world resonate with who operates this product) and **product clarity** (does its grammar carry the product's truth):

| Direction | Audience id | Product clarity | Verdict |
|---|---|---|---|
| **Emission-line rail (spectrograph)** | Strong — a technical operator reading instruments is this audience's own culture | Strong — state-as-line-form is exactly "operational truth"; spectral legend replaces the audit's status-color chaos (C1) | **WINS → build candidate** |
| Generative parametric identity (assigned) | Medium — "brand that reseeds itself" fits reproducible run artifacts | Weak — a self-mutating identity violates principles 1 & 5 (state language must be stable and learnable) | Competitive alternate |
| Film cutting bench | Medium | Medium — superb for run timelines + copilot wizard steps; weaker for ledger/metrics density | Competitive alternate |
| Tensegrity column | Low | Low-medium — constraint-as-tension is poetic but abstract for daily ops | Declined (donates: constraint states rendered as distinct structural states, not badges) |
| Orizuru folds | Low | Medium — step-state visualization maps to the copilot wizard | Declined (donates: wizard step completion states — flat/creased/folded = pending/partial/complete) |
| Leather studio | Low | Low — skeuomorphic warmth conflicts with restraint and no-decoration mandates | Declined |

**Build direction: "Signal Desk"** — the emission-line world, raised by the systems it beat:

- *Raise — parametric token discipline (from the assigned generative identity):* every color, radius, and spacing value derives from one token graph in `index.css`; no literal values in components. The system is parametric in its tokens, not in its identity.
- *Raise — rail grammar (from the cutting bench):* progress and sequence surfaces (pipeline tracker, run timeline, wizard steps) are ticks on a single rail with a position marker.
- *Raise — step-state machine (from orizuru):* the copilot 5-step wizard renders fold-states (pending/partial/complete) instead of active/inactive coloring.
- *Raise — constraint-state rendering (from tensegrity):* policy caps, cooldowns, and dry-run suppression are shown as structural states of the affected rows/cards (struck/dashed/compressed), not as badges on otherwise-normal content.

### The world, in one paragraph

A glass spectrograph on a low viewing bench at 3am: a charcoal continuum crossed by needle-thin spectral lines, every legend at the same tiny size, one sodium pair doubled and standing brighter than anything near it. Career Workflow's console is that instrument: the operator reads pipeline state the way a physicist reads an emission spectrum — line position, line form, line brightness — instead of parsing colored chips. The interface is a calibrated plate: a single off-center rail (navigation), hairline rules, mono annotations, and color that exists only as spectral status lines at seven fixed wavelengths. Nothing glows that isn't a signal. Nothing shadows anything — elevation is line weight and surface step, not drop shadow. "Wow" comes from the density of legible signal, not decoration.

---

## 3. Typography

- **UI + display: Archivo** (variable, 400–700; grotesque with mechanical, instrument-grade structure; not on the default-face list — chosen for its technical grotesque character and strong tabular numerics). Fallback stack: system grotesques.
- **Data + labels + status: JetBrains Mono** (already in the codebase; ligatures off, tabular figures). Keep.
- Faces load self-hosted (fontsource or local `@font-face` with `font-display: swap`) — removes the Google Fonts `@import` first-paint block (audit T1).
- **Type scale (rem-based):**

| Token | Size / weight / case | Use |
|---|---|---|
| `text-index` | 10px mono, uppercase, tracked +10% | Rail indices, coordinate labels, legend |
| `text-label` | 10px mono, uppercase, tracked +8% | Data labels, card indices — accent only, never buttons |
| `text-meta` | 12px | Secondary info, timestamps |
| `text-body` | 13px (base) | UI text, table cells, descriptions |
| `text-emphasis` | 14px, 500–600 | Row titles, list emphasis |
| `text-section` | 16px, 600, tracking -0.01em | Section headers, panel titles |
| `text-page` | 20px, 650, tracking -0.02em | Page titles (replaces text-lg SectionTitle) |
| `text-surface` | 28px, 650, tracking -0.03em | Reserved: metric hero values (Dashboard), never body copy |

- Global: line-height 1.5, letter-spacing -0.01em (relaxed from the current "extremely tight" -0.015em; audit T2). Uppercase is an accent for data labels and indices, not the default voice (audit T5).

---

## 4. Color strategy — "Spectral Continuum" (Restrained; dark-first)

**Physical scene:** one operator, dim room, screen-lit, late-night and early-morning sessions; light mode for daytime use. Dark is default; both themes are designed.

### 4.1 Continuum (neutrals) — dark theme

| Token | Value | Role |
|---|---|---|
| `--background` | `0 0% 5%` | App ground (charcoal continuum) |
| `--surface` | `0 0% 7%` | Panels, cards |
| `--surface-raised` | `0 0% 9%` | Dialogs, sheets, tooltips, hover |
| `--foreground` | `0 0% 93%` | Ink (bone) |
| `--muted-foreground` | `0 0% 60%` | Secondary ink |
| `--faint-foreground` | `0 0% 42%` | Disabled, indices at rest |
| `--border` | `0 0% 16%` | Hairline default |
| `--border-strong` | `0 0% 26%` | Active/emphasized hairline |
| `--primary` | `0 0% 93%` (ink as action) | Primary buttons, active text |
| `--primary-foreground` | `0 0% 5%` | Text on primary |

Light theme mirrors the continuum (background `0 0% 97%`, surface white, ink `0 0% 9%`, borders `0 0% 88%`/`78%`) with status hues adjusted to AA.

### 4.2 Spectral status lines (the fixed 7-wavelength legend)

One legend, used identically across badges, dots, charts, and hairlines. State is **line form first** (§1.2): solid = live, dashed = pending/scheduled, half-height = stale/archived, struck = disabled/blocked, doubled = outranks (single top-priority item on screen).

| Token | λ (nm) | Hue | Semantic |
|---|---|---|---|
| `--spectral-violet` | 405 | `270 84% 66%` | Manual review |
| `--spectral-blue` | 436 | `224 90% 64%` | Info, in-flight |
| `--spectral-cyan` | 486 | `192 92% 56%` | Running / in-progress |
| `--spectral-green` | 546 | `142 71% 45%` | Success, healthy, applied |
| `--spectral-sodium` | 589 | `42 100% 55%` | Warning, pending, priority (doubled form = top priority) |
| `--spectral-orange` | 615 | `24 92% 55%` | Degraded, stale, cooldown |
| `--spectral-red` | 656 | `0 84% 60%` | Error, failed, destructive |

Legacy `--success/--warning/--error/--info` tokens are superseded by the spectral set (mapped in tailwind config as `success/warning/error/info/manual/priority/degraded`). **The ~380 hardcoded `emerald/amber/red/blue/purple` classes in pages are deleted; no raw palette status colors remain** (audit C1). The brand's signature accent is the **doubled sodium line**, used only for the single top-priority item on screen (e.g., the running run, next scheduled execution, high-priority inbox row) — one doubled line per viewport, at most.

### 4.3 Chart palette

`--chart-1..5` become real tokens (defined in `index.css`, mapped in tailwind config — audit C5): spectral-derived sequence for categorical series: 486 cyan, 546 green, 615 orange, 436 blue, 405 violet. No chart colors outside this set. Tooltips render as `--surface-raised` hairline panels (standardize the current per-chart `TOOLTIP_STYLE` into a shared chart tooltip token set).

---

## 5. Surfaces, borders, spacing, radii, elevation

- **Surfaces:** exactly three steps — `background` (ground) → `surface` (panels) → `surface-raised` (overlays/hover). Navigation rail sits on `background` with hairline border; panels on `surface`; dialogs/sheets/tooltips on `surface-raised`.
- **Borders:** hairlines only, 1px, `--border` default / `--border-strong` for active. Opacity dialects (`/40 /50 /60`) collapse to two tokens. No dashed borders except designated empty-state and pending-line states.
- **Spacing:** 4px base grid; container padding 24px (32px ≥1280px); panel padding 16px (20px for detail surfaces); section gap 24px; control gap 8px; table cell padding `10px 16px`. Compact mode (existing `density` setting, currently unused — audit D1) tightens panel padding to 12px and table cells to `8px 12px`; it finally becomes a real setting.
- **Radii:** 4px controls, 6px panels, 8px dialogs/sheets (audit: current global 6px is flattened into a real scale; `--radius` tokens).
- **Elevation: none.** No drop shadows anywhere (formalizes the existing `shadow-card: none` decision). Depth = surface step + border strength + scrim (overlays dim the continuum 40% + blur 2px max). The `shadow-card` no-op utility is deleted.

---

## 6. Component grammar

Full inventory in `UI_COMPONENTS.md`. Grammar rules:

1. **One primitive per structure.** Button, Panel (+PanelHeader), StatusLamp, Table, Tabs, Select, Input, Label, Skeleton→`Scanline`, EmptyState, ErrorState, Toast, Tooltip, Dialog, Sheet, DropdownMenu, ContextMenu (Jobs-only), Checkbox, Command, ScrollArea, Resizable (Jobs-only).
2. **StatusLamp replaces both badge systems** (audit X1): single component, `status` enum → spectral line + label; props `{status, label, line?: 'solid'|'dashed'|'half'|'struck'|'doubled', pulse?}`.
3. **Panel replaces the hand-rolled card idiom** (audit: 12+ files): `Panel` = surface + hairline + 6px; `PanelHeader` = index label (mono) + title + actions; body.
4. **Button variants** become: `primary` (ink), `ghost`, `hairline` (outline), `danger` (656nm). Sizes `sm 28 / md 36 / lg 44`. Live-run CTA: `danger`; dry-run: `primary`; the doubled-sodium form is reserved for priority signals, not buttons.
5. **Tabs** (rebuilt) replace both custom bars and the Pipeline segmented toggle; the toggle becomes a proper radiogroup-style `ToggleGroup` built on Tabs semantics.
6. **Table grammar**: TanStack primitives everywhere (Ledger migrates from raw `<table>` — audit X2); `SortableHeader` gains `aria-sort` and visible sort state; shared density tokens; Jobs keeps virtualization + resizable panels.
7. **Toast** (sonner, already a dependency): single feedback channel for all mutations — launch result, queue transitions, answer locks, copy actions (audit F1).
8. **ConfirmDialog** stays as the only destructive-confirmation wrapper, restyled; all live/destructive mutations route through it (currently only Pipeline does).

---

## 7. Navigation grammar

- **Rail, not list.** The sidebar is the instrument rail: group indices (mono: `01 OPERATIONS`, `02 WORKFLOWS`, `03 COPILOT`, `04 INTELLIGENCE`, `05 TELEMETRY`, `06 DIAGNOSTICS`), items as hairline ticks with labels; active item = full-height ink tick on the rail's left edge (2px, solid) + ink text (replaces the current 0.5px bar + bg-secondary pill). Collapsed = 56px icon rail with tooltips; badge dots use spectral semantics (queue count = sodium, health = cyan/green per state).
- **Breadcrumb = coordinate.** Topbar breadcrumb becomes mono coordinates (`01.03 — PIPELINE`) + page name; keeps the live-state dot (now truthful: spectral line for actual health state, not an always-green pill — audit A7) + ⌘K trigger.
- **Command palette:** keep ⌘K; add actions beyond navigation (launch dry run, open manual-review queue, copy latest run ID). One implementation — delete `components/CommandMenu.tsx` duplicate (audit X3).
- **Mobile (< 900px):** the rail becomes an off-canvas drawer with scrim; topbar gets a menu button; ⌘K remains. Fixes audit R1.
- **Page indices:** every page header carries its mono index (`01 OVERVIEW`) — the coordinate system makes the 24-route surface teachable and gives the instrument identity its spine.

---

## 8. Data visualization grammar

- Charts are instruments: hairline CartesianGrid (only at emphasized ticks), mono axis labels (10px), series = spectral lines (solid primary, dashed secondary), bars with 2px radius and spectral fills, tooltips = `surface-raised` hairline panels. Zero gradients, zero 3D, no decorative chart chrome.
- **PipelineTracker → the Stage Rail:** the signature component. 8 stages as ticks on one hairline rail with a position marker (sodium-doubled when RUNNING); stage state via line form (solid done / half stale / dashed pending / struck failed) + spectral dot. Fixes the three-hue running state (audit C3).
- **Timeline primitive** (shared by Ledger trace, run timeline, copilot session): same rail grammar — events as ticks, current = doubled.
- MetricCard → instrument readout: index label (mono), value in mono tabular numerics at `text-surface`, trend as spectral arrow; no fake click affordance (audit H4).
- Funnel/analytics keep Recharts but all colors from `--chart-1..5`.

---

## 9. Interaction states

- **Focus:** 2px spectral ring (cyan 486) on every interactive element, visible in both themes (audit AX2).
- **Hover:** surface step (raised) + border-strong; never color-only; no scale/translate hover on data.
- **Active/pressed:** 1px ink compression; no bounce.
- **Disabled:** struck form — half-height ink + struck-through where meaningful (live controls while running); plain faint otherwise.
- **Selection:** spectral-green tick (Jobs rows), sodium for priority rows.
- **Drag/resize** (Jobs panels/columns): hairline guides, spectral-green drop indicator.
- **Every icon-only control requires `aria-label`** (audit A2); every clickable row gains keyboard activation (Enter/Space — audit A5); toggle groups expose radiogroup semantics (audit A3).

---

## 10. Loading / empty / error states

- **Loading — `Scanline`:** panels render a hairline skeleton with one horizontal scan-line shimmer (motion grammar, §13); tables render real header + hairline rows with mono "reading…" footer. **No overlay-blur pills** (audit F2); no per-query full-page skeletons except Dashboard's first paint. One primitive replaces all four current idioms.
- **Empty — `EmptyState`:** spectral-dim glyph (single spectral dot at 405 violet or continuum), one-line title, optional single action. Same component on every surface (audit F3).
- **Error — `ErrorState`:** 656nm line + message + retry; page-level boundaries around the 4 mutating/streaming surfaces (Pipeline, Jobs, copilot wizard, Inbox); global boundary restyled. Silent-empty pages get a real error state (audit F4).
- **Mutation feedback:** Toast on completion/failure (§6.8); no optimistic updates until the backend contract supports idempotent replay (out of scope — backend contract frozen).

---

## 11. Responsive rules

- Breakpoints: `sm 640 / md 768 / lg 1024 / xl 1280` (existing Tailwind set). Layout reflow: `900px` nav breakpoint (drawer rail), `1200px` container cap stays `max-w-7xl`.
- Fixed heights removed: Pipeline log and chart panels flex to viewport (audit R3); `h-[520px]`/`h-[240px]` become `h-[clamp(...)]` with the log panel's scroll area owned by the panel.
- Tables: horizontal scroll containers with sticky first column on Jobs/Ledger/Inbox; cell truncation only inside scroll, never data-loss clipping (audit R2).
- Touch targets ≥ 36px minimum (dense tables may use 28px with spacing compensation); badges/labels are non-interactive.
- Light theme verified at all breakpoints (both themes must render, not just collapse).

---

## 12. Accessibility rules

- WCAG 2.1 AA in both themes; status never communicated by hue alone (line form + text label always) — the spectral grammar is inherently dual-channel (audit C1).
- Landmarks kept and completed: skip-link to `#main-content` (audit AX4), `aria-current` on active nav, `aria-live="polite"` on log stream and polling metric regions (audit AX3), `aria-sort` on sortable headers, radiogroup on toggle groups, `aria-label` on all icon-only controls.
- Keyboard: full shell navigation (rail + drawer), row actions via Enter/Space, existing j/k inbox + ⌘K preserved and extended.
- Focus order follows the rail; dialog/sheet focus traps via existing Radix primitives.

---

## 13. Motion rules

Signal language, deliberately small (audit M1 — framer-motion already a dependency, now used):

1. **Scan** — the loading shimmer: one 1.2s horizontal line sweep per panel, `prefers-reduced-motion` → static hairline. 
2. **Pulse** — live-data only: running dot, stage rail position marker (existing `pulse-green` generalized to spectral, audit M2).
3. **Rail slide** — nav active tick and drawer slide: 200ms spring, one overshoot damped (the emission line "landing").
4. **Reveal** — route change only: content fades + 4px rise, 120ms, once per navigation; **no per-item entrance animations on data**, no stagger on tables (data must not re-animate on 5s polls).
5. **Dim** — sheets behind content dim one step (continuum dim + 2px max blur).
- `prefers-reduced-motion`: all motion off (static states remain distinct via line form, not animation).
- No hover animations on data rows, no parallax, no auto-playing charts, no infinite spinners (only pulsing dots for live state).

---

## 14. What NOT to introduce

- No gradients (except the scan shimmer), no glassmorphism/backdrop-blur surfaces beyond the topbar's existing subtle blur (kept optional), no drop shadows, no glow.
- No emoji, no mascots, no illustration, no decorative photography, no ornamental icons.
- No new visual families for status: the 7-wavelength legend is closed; any new state maps into it.
- No parametric identity drift: no per-run or per-data brand mutation (see §1.5; the seeded-identity direction was declined for this reason).
- No new dependencies beyond what `package.json` already declares (sonner, framer-motion, zod, react-hook-form are available); the backend/API contract is frozen — the UI is a pure consumer (no endpoint, schema, or state-management changes).
- No dark-only: light is first-class.
- No per-page redesigns that introduce their own header/table/badge dialects (the audit's core failure mode).

---

## 15. Primitives ↔ page composition

- `components/ui/*` — rebuild the 16 primitives per §6 (delete/rebuild the 4 dead ones: label, select, skeleton, tabs; keep button, checkbox, command, context-menu, dialog, dropdown-menu, input, resizable, scroll-area, sheet, table, tooltip).
- `components/operations/*` — the shared "instrument kit": SectionTitle (→ page header w/ index), MetricCard/MetricGrid (→ readouts), StatRow, StatusLamp.
- `components/domain/*` (new) — page-specific composites built from primitives: `PipelineStageRail`, `Timeline`, `CoverageMatrix`, `WizardSteps`, `JobTable`, `QueueTable`, `BriefView`, `AssistantPanel`, `AnswerBankTable`.
- Pages import only primitives + kits + domain composites; page files shrink (Apply 1515 lines and Assistant 1110 lines get decomposed into domain composites — behavior-preserving extraction).
- Composition rule: a page may define layout and page-specific data logic, but **no chrome** (headers, badges, loading, empty, error, borders) inline.

---

## 16. Redesign implementation order

1. **Design tokens** — rewrite `index.css` (spectral tokens, type scale, spacing, radii, elevation-null), `tailwind.config.js` (map spectral + chart + size tokens), delete `App.css` duplicate scrollbar + `shadow-card` no-op; self-host fonts.
2. **Application shell** — `Layout`, `Sidebar` (rail grammar + indices), `Topbar` (coordinates + truthful live state), `ThemeProvider` (both themes), mobile drawer.
3. **Navigation** — nav indices, collapsed rail, drawer, ⌘K actions; delete duplicate CommandMenu.
4. **Shared primitives** — Button, Panel/PanelHeader, StatusLamp (kills both badges), Table grammar, Tabs/ToggleGroup, Select/Input/Label, Scanline, EmptyState, ErrorState, Toast, ConfirmDialog restyle.
5. **Representative page: Dashboard (Overview)** — establishes the language end-to-end: page header/index, stage rail, metric readouts, funnel chart, activity feed, Scanline, EmptyState, live-state dot. This page exercises every token class and becomes the visual validation target.
6. **Visual validation** — screenshot round (desktop + mobile) against this contract; run `npm run gate` (typecheck/lint/build) green; one fix batch max.
7. **Remaining pages**, in dependency order: Ledger (table+sheet grammar) → Jobs (virtualized table, context menu, resizable) → Pipeline (action surface, ToggleGroup, ConfirmDialog, log panel) → copilot Brief + Inbox (evidence dossier + triage rail) → Intelligence, Metrics, Applications, Runs, System, Providers → Logs, Explorer, Audit, Configuration, Developer, About → copilot Apply + Assistant (wizard + assistant panels, largest, last).
8. **Responsive pass** — drawer nav, table sticky columns/scroll, viewport-flexible heights, touch targets.
9. **Accessibility pass** — resolve every audit AX item (skip link, aria-sort, radiogroups, live regions, icon labels, row keyboard access).
10. **Motion pass** — signal grammar (§13) + reduced-motion.
11. **Final Impeccable audit** — mechanical detector (`detect.mjs`) + critique against this contract; fix batch; document the shipped system (finish review per Impeccable flow), then cleanup dead files (CommandMenu dup, CopilotPlaceholder, keyword StatusBadge).

**Non-goals for this redesign:** backend/API/data-model/state changes (frozen contract); new features; dependency changes; performance work beyond what the token/font changes touch.
