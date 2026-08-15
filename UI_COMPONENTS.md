# UI Components — Career Workflow Next

Existing inventory (verified from source) + the proposed component grammar (future system; full contract in DESIGN.md).

## Part 1 — Existing inventory

### `components/ui/*` (16 shadcn-style primitives) and usage count (import sites outside the file)

| Primitive | Uses | Notes |
|---|---|---|
| button | 13 | cva variants: default/destructive/outline/secondary/ghost/link; sizes default/sm/lg/icon. Pages frequently override with raw classes (e.g. `h-7 text-[11px]`) instead of size variants — variant drift. |
| badge | 3 | shadcn badge — **but pages mostly use custom StatusBadge instead** (inconsistent). |
| card | 1 | shadcn Card barely used; pages build their own `bg-card border rounded-md shadow-card` wrappers everywhere → duplicated card idiom in ~12 files. |
| checkbox | 2 | Jobs + Pipeline. |
| command | 2 | ⌘K palette (App.tsx + components/CommandMenu.tsx duplicate). |
| context-menu | 1 | Jobs. |
| dialog | 3 | ConfirmDialog, Jobs JSON dialog. |
| dropdown-menu | 1 | Jobs column toggle. |
| input | 5 | search/filters/ceiling. |
| label | 0 | **dead** (forms use raw `<label>`). |
| resizable | 2 | Jobs panels. |
| scroll-area | 7 | Ledger sheet, Jobs, copilot pages. |
| select | 0 | **dead** — Ledger + copilot/Inbox use raw `<select>`. |
| sheet | 4 | Ledger trace, Inbox brief, Applications. |
| skeleton | 0 | **dead** — pages hand-roll `animate-pulse` divs. |
| tabs | 0 | **dead** — Applications/Logs use custom tab bars. |
| table | 4 | TanStack Table primitives (Jobs). Ledger uses raw `<table>`. |
| tooltip | 2 | RelativeTime, CopyButton (relative imports). |

Dead primitives: `label`, `select`, `skeleton`, `tabs` (4 of 16). Parallel/custom implementations exist for badge (2 StatusBadges), tabs (2 custom bars), dialog (ConfirmDialog vs Dialog), command (2 ⌘K copies).

### Shared components (non-ui)

- `operations/` kit: MetricCard/MetricGrid, SectionTitle, StatRow, StatusBadge (generic). Used by Dashboard/Pipeline/Ledger/Intelligence/Runs/Providers — the closest thing to a shared system; it is the de-facto design language (uppercase 10px labels, hairline cards, mono values).
- `StatusBadge.tsx` (keyword map, 90 lines) vs `operations/StatusBadge.tsx` (generic, 37 lines) — **two badge systems, different props, both live**; 15 files import one of the two.
- `JobDrawer.tsx` — detail drawer shared by Inbox + Applications.
- `ConfirmDialog.tsx` — only destructive-confirmation guard in the app.
- `RelativeTime.tsx` — date-fns + tooltip absolute time; used ~8 files. Good pattern, keep.
- `CopyButton.tsx`, `SortableHeader.tsx`, `ErrorBoundary.tsx`, `CommandMenu.tsx` (unused duplicate of App.tsx's).
- Dead files: `pages/copilot/CopilotPlaceholder.tsx`.

### Duplication register (worst offenders)

1. Card idiom: `bg-card border border-border rounded-md shadow-card` + header row (`px-4 py-3 border-b` + 11px uppercase label) repeated by hand in ≥12 files (Dashboard, Pipeline, Ledger, Intelligence, Metrics, System, Providers, copilot/*…). No `Card` wrapper used (ui/card usage = 1).
2. Status colors: ~380 hardcoded `emerald/amber/red/blue/purple/zinc` classes across src (grep, 2026-08-15) vs 4 defined-but-unused `--success/--warning/--error/--info` tokens.
3. Section header pattern (SectionTitle) is shared, but table headers, card headers, panel headers each re-declare the 10px uppercase style inline.
4. Provider identity maps: `PROVIDER_META` (Intelligence) vs `PROVIDER_ICONS`+`PROVIDER_COLORS` (Providers) — two parallel maps.
5. Lifecycle color maps: Dashboard LIFECYCLE_LABELS, Metrics LIFECYCLE_COLORS + TOOLTIP_STYLE, Ledger status→badge mapping inline twice in one file.
6. Log terminal panels: Pipeline `bg-[#0a0a0a]`, Ledger `bg-[#0a0a0a]`, Logs `bg-[#0d1117]`, ErrorBoundary `bg-[#0a0a0a]` — 3 distinct hardcoded dark backgrounds.
7. ⌘K command menu: defined in App.tsx AND components/CommandMenu.tsx.
8. Loading idioms: skeleton blocks (Dashboard), overlay pill (Ledger), pulse text (Pipeline), spinner (Jobs) — no shared primitive.
9. `Briefcase` custom SVG fn in Jobs.tsx:772 shadows the lucide `Briefcase` import name in the same file.

## Part 2 — Proposed component grammar (future system)

The future system (DESIGN.md, "Signal Desk" direction) replaces ad-hoc composition with a small, strict component set. Principle: **one way to express each structure**; pages compose, never re-implement.

### Primitives (rebuilt)

| Primitive | Contract |
|---|---|
| `Button` | Keep cva, but variants become: `primary` (ink on bone), `ghost`, `danger` (656nm), `hairline` (outline). Sizes map to a real 8px scale (sm 28 / md 36 / lg 44). No per-call class overrides; `--button-*` tokens own height/radius/ink. |
| `Badge` / `StatusLamp` | ONE badge: `StatusLamp` renders spectral line + label from a single status enum (success/warning/error/info/neutral/running/manual). Replaces both StatusBadges and the shadcn badge. State via spectral hue + line form (solid/dashed/half-height). |
| `Card`/`Panel` | ONE panel primitive with `PanelHeader` (title, mono index, actions) — kills the hand-rolled card idiom. Hairline border, no shadow, 6px radius. |
| `Table` | One table grammar on TanStack primitives; `SortableHeader` gains `aria-sort`; row selection/virtualization stay Jobs-only. Ledger's raw table migrates. |
| `Tabs` | One tab primitive (unused ui/tabs rebuilt to grammar) — replaces both custom bars + Pipeline segmented toggle. |
| `Select`/`Input`/`Label` | Rebuild dead ui/select, ui/label; form fields adopt `--input-*` tokens. |
| `Skeleton` | Rebuild as `Scanline` loading primitive (motion grammar, DESIGN.md) — replaces all four loading idioms. |
| `EmptyState` | NEW shared component (icon + title + action) — one empty-state language. |
| `ErrorState` | NEW shared component (inline + banner variants) + per-surface error boundaries. |
| `Toast` | NEW (sonner is already a dependency) — first feedback channel; launch result, queue transitions, answer locks. |
| `MetricCard` | Keep concept; values become instrument readouts (mono, tabular-nums, index label). |
| `PipelineTracker` | Rebuilt as the stage rail (rail grammar) — the product's signature component. |
| `Timeline` | NEW — event timelines (Ledger trace, run timeline, copilot session) share one rail grammar. |
| `RelativeTime`, `CopyButton`, `ConfirmDialog` | Preserve behavior; restyle to grammar. |

### Composition rules

1. Pages import primitives + `operations/` kits only; no page-local re-implementation of chrome (borders, headers, badges, loading).
2. Page-specific composite components (Jobs table, wizard steps, coverage matrix) live in `components/<domain>/` and compose primitives.
3. Two layout containers only: shell `Layout` (sidebar+topbar+main) and `SectionTitle`-replacement page header — no third header idiom.
4. State surfaces (loading/empty/error) are primitives, not inline classes.

### What this deletes (dead weight)

- `components/CommandMenu.tsx` (dup), `components/StatusBadge.tsx` keyword variant, `pages/copilot/CopilotPlaceholder.tsx`, `App.css` duplicate scrollbar block, `--chart-1..5` config stub, `shadow-card` no-op utility, unused `label/select/skeleton/tabs` primitives get rebuilt or removed.
