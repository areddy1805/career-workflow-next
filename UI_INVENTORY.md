# UI Inventory — Career Workflow Next (frontend)

_Verified against source 2026-08-15. This describes the ACTUAL repository, not assumptions. See UI_AUDIT.md for findings, UI_ROUTES.md for the route table, UI_COMPONENTS.md for the component system, DESIGN.md for the proposed future system._

## 1. Stack (verified in `frontend/package.json`, configs)

| Concern | Actual | Notes |
|---|---|---|
| Framework | React 19.2 (react, react-dom) | — |
| Language | TypeScript ~6.0.2 | `tsc -b` typecheck script |
| Build | Vite 8.1.x | `vite.config.ts`: `@` → `./src`, dev port 5173 strict, proxy `/api` → `http://127.0.0.1:8090` |
| Package manager | npm | `package-lock.json` present; scripts: dev, typecheck, build, lint (oxlint), gate, preview |
| Styling | Tailwind CSS 3.4 (`tailwind.config.js`, darkMode `["class"]`) + postcss + autoprefixer + tailwindcss-animate | HSL CSS-variable tokens via shadcn convention |
| Routing | react-router-dom 7.18 (BrowserRouter, no lazy loading) | 24 routes, all eager |
| Data fetching | @tanstack/react-query 5 (single `QueryClient`, staleTime 30s, no window-focus refetch) | polling-heavy |
| State | zustand 5 (3 stores: preferences, jobs, copilot) | persist middleware on preferences + jobs |
| Tables | @tanstack/react-table 8 + @tanstack/react-virtual | Jobs page only |
| Charts | recharts 3.9 | Dashboard funnel, Metrics |
| Forms | react-hook-form 7.81 + zod 4 | **declared, UNUSED in src** (verified 0 imports) |
| Toasts | — | **no toast system at all** (sonner declared in package.json, UNUSED) |
| Motion | framer-motion 12 | **declared, UNUSED in src** (verified 0 imports); only CSS `animate-pulse`/`animate-in` used |
| Icons | lucide-react (40 files import it) | one custom SVG icon (`Briefcase` fn in Jobs.tsx:772, shadows lucide name) |
| UI primitives | shadcn-style `components/ui/*` (16 files) | several are dead (see UI_COMPONENTS.md) |
| Dates | date-fns 4 | `RelativeTime` component |
| Misc | react-resizable-panels (Jobs), radix primitives via ui/*, cmdk via ui/command, react18-json-view, react-error-boundary, cva, tailwind-merge/clsx (`cn`) | — |

## 2. Entry & shell (`src/main.tsx`, `src/App.tsx`)

- `main.tsx`: StrictMode + `<App/>` only (no providers at entry).
- `App.tsx` (445 lines): GlobalErrorBoundary → QueryClientProvider (staleTime 30s) → ThemeProvider (zustand theme → adds `light`/`dark` class to `<html>`) → Router → CommandMenu (⌘K) + Layout.
- Layout: fixed `h-screen` flex; Sidebar (240px / 58px collapsed, z-40) + Topbar (h-12 sticky, breadcrumb, live-status pill, ⌘K trigger) + `<main class="p-6 lg:p-8 max-w-7xl mx-auto">`.
- Sidebar: 6 nav groups (Operations Center, Workflows, Copilot, Intelligence, Telemetry, Diagnostics), 24 nav items + Settings + Collapse toggle. Live badges: Applications = queue count, Copilot Inbox = subsystem-health count.
- Command palette (`CommandMenu` in App.tsx): ⌘K/ctrl+K, navigation-only (no command actions).
- No mobile navigation: sidebar is fixed-width at all breakpoints; no drawer for small screens (see P1 findings).
- No lazy routes, no route guards, no catch-all/404 route.

## 3. Styling system & tokens (`src/index.css`)

- Google Fonts `@import`: Inter 400/500/600 + JetBrains Mono 400/500.
- HSL token set in `:root` + `.dark` (shadcn default-slate base, `baseColor: slate` per components.json): `--background, --foreground, --card, --card-foreground, --popover, --popover-foreground, --primary, --primary-foreground, --secondary, --secondary-foreground, --muted, --muted-foreground, --accent, --accent-foreground, --destructive, --destructive-foreground, --border, --input, --ring, --radius` (0.375rem).
- Custom semantic status tokens defined: `--success: 142 71% 45%`, `--warning: 38 92% 50%`, `--error: 0 84% 60%`, `--info: 212 96% 61%` — **defined in CSS but NOT mapped in tailwind.config.js and NOT consumed anywhere** (status colors are hardcoded tailwind palette classes instead; see UI_AUDIT P2-1).
- `tailwind.config.js` maps `chart.1–5` to `hsl(var(--chart-1))…` — **the `--chart-1..5` vars are never defined in index.css** and recharts usages pass raw colors in the components (Dashboard/Metrics use `hsl(var(--border))` etc. in tooltips; series colors are inline).
- Base layer: `* { @apply border-border }`; body: Inter, line-height 1.6, `letter-spacing: -0.015em` ("Extremely tight" per comment); `.font-mono, code, pre, kbd` → JetBrains Mono with ligatures off.
- Scrollbars: 4px webkit scrollbar in index.css (radius 99px) AND a duplicate `custom-scrollbar` block in `App.css` (radius 2px) — two parallel scrollbar styles, inconsistent radius.
- Utilities: `.shadow-card { box-shadow: none }` (both themes — deliberate flatness), `.pulse-green` keyframes.
- Dark is the default (`usePreferences` default `theme: 'dark'`; `index.html` also has hardcoded `class="dark"`). Light mode exists via toggle but is visually unmaintained.
- Fonts are loaded from Google Fonts at runtime (`@import` in CSS) — network dependency; no self-hosting, no `font-display` control.

## 4. State (`src/store/`)

- `preferences.ts` (persist `cw-preferences`): theme ('dark' default), density ('compact' default — the 'comfortable' option exists but is unused), sidebarOpen.
- `jobs.ts` (persist `cw-jobs-state`): TanStack sorting + columnVisibility + filters for the Jobs table.
- `copilot.ts`: workspace wizard state (step: brief→answers→resume→assistant→submit), opportunityId/sessionId binding, inline-answer edit state. Not persisted.

## 5. Data layer (`src/lib/`)

- `api/base.ts`: single `fetchApi` wrapper — relative `/api` base (vite proxy), JSON headers, 90s AbortController timeout, error envelope parsing (copilot `{ok,error:{message}}` then `{detail}` then `{message}`).
- `api/index.ts`: barrel over 14 endpoint modules. Endpoint inventory (all under `/api`):
  - dashboard, jobs, jobs/:id, runs, runs/:id, runs/:id/artifacts, runs/:id/artifacts/:file, artifacts, runtime, settings, pipeline/state, pipeline/launch (POST), ledger/search, ledger/stats, ledger/job/:fp, search-intelligence, metrics, queues/manual-review, queues/external-apply, queues/other-action, queues/:jobId/transition (POST), queues/:jobId/move (POST), audit/pipeline, audit/filters, audit/ranking, audit/system, audit/explain, logs/pipeline|runtime|eventbus|errors|warnings|ledger|search, providers, system, developer, copilot/health, copilot/opportunities, copilot/opportunities/:id, copilot/briefs/:id, copilot/sessions (GET/POST), copilot/sessions/:id, copilot/answers, copilot/answers/:fp (PUT), copilot/answers/confirm (POST), copilot/answers/lock (POST), copilot/profiles/switch (POST), copilot/analytics, copilot/browser/open|form|fill|submit|checkpoint (POST), /api/v1/viewmodel.
- `hooks.ts`: ~30 typed `useQuery` hooks. Polling: dashboard 5s, viewmodel 1s, pipeline/state 3s, metrics 5s, logs* 5s, system 5s, developer 5s, providers 10s, ledger/stats 10s, queues 15s, copilot opportunities/analytics 30s, session 1s while active.
- Mutations: `useMutation` only in Pipeline.tsx (launch). Queue transitions/moves and copilot answer/browser actions call `fetchApi` directly from components (no mutation abstraction, no cache invalidation wiring for those).

## 6. Pages (24) — see UI_ROUTES.md for the full table

Dashboard 314 · Pipeline 265 · Jobs 780 · Runs 200 · Ledger 303 · Applications 233 · Intelligence 362 · Explorer 195 · Metrics 267 · Audit 79 · Configuration 71 · Logs 99 · Providers 142 · System 218 · Developer 115 · About 67 · copilot/Inbox 766 · copilot/Apply 1515 · copilot/Brief 197 · copilot/Assistant 1110 · copilot/History 251 · copilot/Analytics 482 · copilot/Learning 670 · copilot/Settings 277 · (copilot/CopilotPlaceholder 38 — **unused, dead file**). Total ~9.8k lines.

## 7. Shared components (non-ui)

- `components/operations/`: MetricCard + MetricGrid, SectionTitle, StatRow, StatusBadge (generic status-type).
- `components/StatusBadge.tsx`: **second, parallel badge** — status-keyword → color map (APPLIED/SUBMITTED/HEALTHY/REJECTED/RUNNING…), mono uppercase. Both badge systems are used across pages (8 files use the keyword one, 7 use the generic one).
- `JobDrawer.tsx` (223): used by copilot/Inbox + Applications.
- `ConfirmDialog.tsx` (61): Dialog wrapper for destructive confirmations (Pipeline live run).
- `CommandMenu.tsx` (63): separate copy of the ⌘K dialog (also defined in App.tsx — duplication; App.tsx imports from ui/command and implements its own; the components/CommandMenu.tsx file appears unused).
- `CopyButton.tsx`, `RelativeTime.tsx` (tooltip + date-fns), `SortableHeader.tsx`, `ErrorBoundary.tsx` (global + inline `any` fallbacks).

## 8. Accessibility snapshot

- Landmarks: sidebar `aria-label="Main navigation"`, topbar `role="banner"`, breadcrumb nav aria-label, main `id="main-content"`.
- Icon-only buttons: 23 candidate spots without aria-label (audit estimate; e.g. sidebar collapse has aria-label, several table action icons rely on title/text).
- Focus: shadcn ui/* include focus-visible rings; custom controls (segmented toggle in Pipeline, SortableHeader clickable `<th>`, raw `<select>`s in Ledger/Inbox, Ledger table rows as click targets) lack keyboard affordance.
- Tables: Ledger uses raw `<table>` (sortable? no); Jobs uses TanStack + virtualized rows; a11y roles not asserted (`aria-sort` absent in SortableHeader).
- Dark-only visual QA historically; light theme contrast unverified.

## 9. Responsive snapshot

- Layout is desktop-first, `h-screen` shell; sidebar never collapses to a drawer; `<main>` padding p-6/lg:p-8; grids use sm:/lg: breakpoints (MetricGrid, Dashboard 2-col, Pipeline 1-col→lg 2-col).
- Tables: Jobs virtualized table relies on column sizing + horizontal scroll; Ledger table truncates cells (max-w) with no horizontal scroll container — overflow risk on narrow screens.
- No mobile menu; topbar breadcrumb + ⌘K persist at all widths. No touch-target sizing (many 4-8px controls).
