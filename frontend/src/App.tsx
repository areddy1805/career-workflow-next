import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import {
  LayoutDashboard, Briefcase, Play, Inbox, Search, Settings, PlaySquare,
  BarChart2, Server, BookOpen, Brain, Activity, Terminal, Wrench, Shield,
  PanelLeftClose, PanelLeftOpen, Menu, X, History, TrendingUp, GraduationCap, Cog,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePreferences } from '@/store/preferences';
import { GlobalErrorBoundary } from '@/components/ErrorBoundary';
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput,
  CommandItem, CommandList,
} from '@/components/ui/command';
import { fetchManualReviewQueue, fetchExternalApplyQueue } from '@/lib/api';
import { useCopilotHealth, useRuntime } from '@/lib/hooks';
import { StateMarker, type StateSemantic } from '@/components/operations/StateMarker';
import { Toaster } from '@/components/operations/Toaster';

import Dashboard from '@/pages/Dashboard';
import Jobs from '@/pages/Jobs';
import Pipeline from '@/pages/Pipeline';
import Runs from '@/pages/Runs';
import Ledger from '@/pages/Ledger';
import Applications from '@/pages/Applications';
import Intelligence from '@/pages/Intelligence';
import Explorer from '@/pages/Explorer';
import Metrics from '@/pages/Metrics';
import Audit from '@/pages/Audit';
import Configuration from '@/pages/Configuration';
import Logs from '@/pages/Logs';
import Providers from '@/pages/Providers';
import System from '@/pages/System';
import Developer from '@/pages/Developer';
import About from '@/pages/About';
import CopilotInbox from '@/pages/copilot/Inbox';
import CopilotApply from '@/pages/copilot/Apply';
import CopilotBrief from '@/pages/copilot/Brief';
import CopilotAssistant from '@/pages/copilot/Assistant';
import CopilotHistory from '@/pages/copilot/History';
import CopilotAnalytics from '@/pages/copilot/Analytics';
import CopilotLearning from '@/pages/copilot/Learning';
import CopilotSettings from '@/pages/copilot/Settings';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
});

// ─── Information Architecture (unchanged — Grid Control chrome only) ─────────

const NAV_GROUPS: Array<{ index: string; label: string; items: Array<{ name: string; path: string; icon: React.ComponentType<{ className?: string }>; badge?: 'queue' | 'health' }> }> = [
  {
    index: '01',
    label: 'Operations',
    items: [
      { name: 'Overview',       path: '/',              icon: LayoutDashboard },
      { name: 'Pipeline',       path: '/pipeline',      icon: Play            },
      { name: 'Runs',           path: '/runs',          icon: PlaySquare      },
    ],
  },
  {
    index: '02',
    label: 'Workflows',
    items: [
      { name: 'Jobs',           path: '/jobs',          icon: Briefcase },
      { name: 'Applications',   path: '/applications',  icon: Inbox, badge: 'queue' },
    ],
  },
  {
    index: '03',
    label: 'Copilot',
    items: [
      { name: 'Inbox',          path: '/copilot/inbox', icon: Inbox, badge: 'health' },
      // Apply/Brief/Assistant are parameter routes — reachable only with a
      // real id from the Inbox row / Brief CTA / workspace assistant link.
      { name: 'History',        path: '/copilot/history',   icon: History       },
      { name: 'Analytics',      path: '/copilot/analytics', icon: TrendingUp    },
      { name: 'Learning',       path: '/copilot/learning',  icon: GraduationCap },
      { name: 'Settings',       path: '/copilot/settings',  icon: Cog           },
    ],
  },
  {
    index: '04',
    label: 'Intelligence',
    items: [
      { name: 'Decision Ledger', path: '/ledger',       icon: BookOpen },
      { name: 'AI Insights',     path: '/intelligence', icon: Brain    },
      { name: 'Explorer',        path: '/explorer',     icon: Search   },
    ],
  },
  {
    index: '05',
    label: 'Telemetry',
    items: [
      { name: 'Metrics',        path: '/metrics',       icon: BarChart2 },
      { name: 'Providers',      path: '/providers',     icon: Server    },
    ],
  },
  {
    index: '06',
    label: 'Diagnostics',
    items: [
      { name: 'System Health',  path: '/system',        icon: Activity },
      { name: 'Logs',           path: '/logs',          icon: Terminal },
      { name: 'Developer Tools', path: '/developer',    icon: Wrench   },
      { name: 'Audit',          path: '/audit',         icon: Shield   },
    ],
  },
];

const ALL_NAV_ITEMS = NAV_GROUPS.flatMap(g => g.items);
const EXTRA_NAV = [
  { name: 'Settings', path: '/config' },
  { name: 'About', path: '/about' },
];

// ─── Inbox badge count ───────────────────────────────────────────────────────

function useInboxCount() {
  const { data: manual } = useQuery({
    queryKey: ['queue', 'manual-review'],
    queryFn: fetchManualReviewQueue,
    staleTime: 60_000,
  });
  const { data: external } = useQuery({
    queryKey: ['queue', 'external-apply'],
    queryFn: fetchExternalApplyQueue,
    staleTime: 60_000,
  });
  const count = (manual?.items?.length ?? 0) + (external?.items?.length ?? 0);
  return count > 0 ? count : null;
}

// Copilot Inbox badge: subsystem-health driven (existing contract, preserved).
function useCopilotHealthBadge(): number | string | null {
  const { data, isError } = useCopilotHealth();
  if (isError) return '!';
  if (!data) return null;
  if (data.ok) return null;
  const down = Object.values(data.data?.subsystems ?? {}).filter(s => s !== 'ok').length;
  return down > 0 ? down : '!';
}

// ─── Truthful runtime status (DESIGN.md §4 — no always-green pill) ───────────

const SCHEDULER_STATE: Record<string, { state: StateSemantic; pulse?: boolean }> = {
  RUNNING: { state: 'running', pulse: true },
  IDLE: { state: 'idle' },
  STOPPED: { state: 'blocked' },
  STALE: { state: 'degraded' },
  ORPHANED: { state: 'failed' },
};

function SystemStatus() {
  const { data, isError, isFetching } = useRuntime();
  const status = data?.scheduler?.status ?? (isError ? 'UNREACHABLE' : '…');
  const mapped = SCHEDULER_STATE[status] ?? { state: 'unknown' as StateSemantic };
  return (
    <span
      className="inline-flex items-center gap-1.5"
      aria-live="polite"
      aria-label={`System status: ${status}`}
      title={`Scheduler: ${status}`}
    >
      <StateMarker state={mapped.state} label={status} pulse={mapped.pulse && !isFetching} />
    </span>
  );
}

// ─── Sidebar rail ─────────────────────────────────────────────────────────────

function RailContent({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const inboxCount = useInboxCount();
  const copilotBadge = useCopilotHealthBadge();

  return (
    <>
      {/* Wordmark */}
      <div className={cn('h-11 border-b border-border flex items-center shrink-0', collapsed ? 'justify-center px-0' : 'px-3')}>
        {collapsed ? (
          <span className="w-6 h-6 flex items-center justify-center" aria-label="Career Workflow">
            <svg width="16" height="16" viewBox="0 0 12 12" className="text-foreground" aria-hidden="true">
              <rect x="2" y="2" width="8" height="8" fill="currentColor" />
              <rect x="4.5" y="4.5" width="3" height="3" fill="var(--background)" />
            </svg>
          </span>
        ) : (
          <div className="flex items-center gap-2.5 overflow-hidden whitespace-nowrap">
            <span className="w-6 h-6 flex items-center justify-center shrink-0">
              <svg width="16" height="16" viewBox="0 0 12 12" className="text-foreground" aria-hidden="true">
                <rect x="2" y="2" width="8" height="8" fill="currentColor" />
                <rect x="4.5" y="4.5" width="3" height="3" fill="var(--background)" />
              </svg>
            </span>
            <div>
              <p className="text-sm font-semibold tracking-tight leading-none text-foreground">Career Workflow</p>
              <p className="text-[9px] text-faint font-mono tracking-[0.14em] mt-1">CONTROL PLANE</p>
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2.5 py-4 flex flex-col gap-5 overflow-y-auto overflow-x-hidden" aria-label="Main navigation">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <p className="flex items-center gap-2 text-[10px] font-medium text-faint font-mono uppercase tracking-[0.1em] px-2 mb-1.5">
                <span aria-hidden="true">{group.index}</span>
                <span className="text-muted-foreground/70">{group.label}</span>
              </p>
            )}
            <div className="flex flex-col">
              {group.items.map(item => (
                <RailItem
                  key={item.path}
                  item={item}
                  collapsed={collapsed}
                  badge={item.badge === 'queue' ? inboxCount : item.badge === 'health' ? copilotBadge : null}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-2.5 py-2.5 border-t border-border flex flex-col">
        {EXTRA_NAV.map(extra => (
          <NavLink
            key={extra.path}
            to={extra.path}
            title={collapsed ? extra.name : undefined}
            onClick={onNavigate}
            className={({ isActive }) => cn(
              'flex items-center gap-3 px-2 py-1.5 rounded-sm text-[13px] font-medium whitespace-nowrap relative',
              isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {({ isActive }) => (
              <>
                {isActive && <ActiveTick />}
                {!collapsed && <span className="tracking-tight">{extra.name}</span>}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </>
  );
}

function ActiveTick() {
  return (
    <span
      className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 bg-foreground"
      aria-hidden="true"
    />
  );
}

function RailItem({
  item, collapsed, badge, onNavigate,
}: {
  item: typeof ALL_NAV_ITEMS[0];
  collapsed: boolean;
  badge?: number | string | null;
  onNavigate?: () => void;
}) {
  return (
    <NavLink
      to={item.path}
      end={item.path === '/'}
      title={collapsed ? item.name : undefined}
      onClick={onNavigate}
      className={({ isActive }) => cn(
        'flex items-center gap-3 px-2 py-[7px] rounded-sm text-[13px] font-medium whitespace-nowrap relative transition-colors',
        isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
      )}
    >
      {({ isActive }) => (
        <>
          {isActive && <ActiveTick />}
          <item.icon className={cn('w-4 h-4 shrink-0', isActive ? 'text-foreground' : 'text-muted-foreground')} aria-hidden="true" />
          {!collapsed && <span className="flex-1 tracking-tight">{item.name}</span>}
          {!collapsed && badge != null && (
            <span className="ml-auto text-[9px] font-bold bg-muted text-foreground px-1.5 py-0.5 rounded-full min-w-[18px] text-center leading-none">
              {typeof badge === 'number' && badge > 99 ? '99+' : badge}
            </span>
          )}
          {collapsed && badge != null && (
            <span
              className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-foreground"
              aria-label={`${badge} items`}
            />
          )}
        </>
      )}
    </NavLink>
  );
}

// ─── Sidebar (desktop rail) ──────────────────────────────────────────────────

function Sidebar() {
  const { sidebarOpen, toggleSidebar } = usePreferences();
  return (
    <aside
      className={cn(
        'hidden lg:flex border-r border-border bg-surface h-screen flex-col shrink-0 relative z-30 transition-[width] duration-200 ease-out',
        sidebarOpen ? 'w-[224px]' : 'w-[56px]'
      )}
      aria-label="Main navigation"
    >
      <RailContent collapsed={!sidebarOpen} />
      <div className="px-2.5 pb-2.5 border-t border-border">
        <button
          onClick={toggleSidebar}
          aria-label={sidebarOpen ? 'Collapse navigation rail' : 'Expand navigation rail'}
          className="flex items-center gap-3 px-2 py-1.5 w-full rounded-sm text-[12px] text-muted-foreground hover:text-foreground transition-colors"
        >
          {sidebarOpen ? <PanelLeftClose className="w-4 h-4 shrink-0" aria-hidden="true" /> : <PanelLeftOpen className="w-4 h-4 shrink-0" aria-hidden="true" />}
          {sidebarOpen && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}

// ─── Mobile drawer (< lg) ────────────────────────────────────────────────────

function MobileDrawer() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => setOpen(false), [location.pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open]);

  return (
    <>
      <button
        className="lg:hidden inline-flex items-center justify-center h-9 w-9 rounded-sm text-foreground hover:bg-secondary transition-colors"
        onClick={() => setOpen(true)}
        aria-label="Open navigation menu"
      >
        <Menu className="w-4 h-4" aria-hidden="true" />
      </button>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button
            className="absolute inset-0 bg-black/50"
            onClick={() => setOpen(false)}
            aria-label="Close navigation menu"
            tabIndex={-1}
          />
          <aside className="absolute left-0 top-0 bottom-0 w-[264px] bg-surface border-r border-border flex flex-col shadow-none">
            <button
              className="absolute right-2 top-2 inline-flex items-center justify-center h-8 w-8 rounded-sm text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setOpen(false)}
              aria-label="Close navigation menu"
              autoFocus
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
            <RailContent collapsed={false} onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
    </>
  );
}

// ─── Topbar ──────────────────────────────────────────────────────────────────

function Topbar() {
  const location = useLocation();
  const crumbs = buildBreadcrumb(location.pathname);

  return (
    <header
      className="h-11 border-b border-border bg-background flex items-center px-3 lg:px-4 justify-between shrink-0 z-30 sticky top-0"
      role="banner"
    >
      <div className="flex items-center gap-2 min-w-0">
        <MobileDrawer />
        <nav aria-label="Breadcrumb" className="min-w-0">
          <ol className="flex items-center gap-2 text-[13px] whitespace-nowrap overflow-hidden">
            {crumbs.map((crumb, i) => (
              <li key={crumb.label} className="flex items-center gap-2 min-w-0">
                {i > 0 && <span className="text-faint font-mono text-[10px]" aria-hidden="true">/</span>}
                <span className={cn(
                  'truncate',
                  i === crumbs.length - 1
                    ? 'font-semibold text-foreground tracking-tight'
                    : 'text-muted-foreground font-mono text-[10px] uppercase tracking-[0.1em]'
                )}>
                  {crumb.label}
                </span>
              </li>
            ))}
          </ol>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        <SystemStatus />
        <CommandTrigger />
      </div>
    </header>
  );
}

function buildBreadcrumb(pathname: string) {
  const all = [...ALL_NAV_ITEMS, ...EXTRA_NAV];
  const match = all.find(i => i.path === pathname);
  if (match) {
    const group = NAV_GROUPS.find(g => g.items.some(i => i.path === match.path));
    return [
      { label: group ? `${group.index} · ${group.label}` : 'OPS' },
      { label: match.name },
    ];
  }
  // parameter routes (copilot apply/brief/assistant) — keep group context
  const prefix = pathname.split('/').filter(Boolean)[0];
  const group = NAV_GROUPS.find(g => g.items.some(i => i.path.startsWith(`/${prefix}`)));
  return [
    { label: group ? `${group.index} · ${group.label}` : 'OPS' },
    { label: pathname.slice(1) || 'Overview' },
  ];
}

function CommandTrigger() {
  return (
    <button
      className="flex items-center gap-2 text-xs text-muted-foreground border border-border hover:border-borderStrong bg-surface px-2.5 py-1.5 rounded-sm transition-colors"
      onClick={() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
      aria-label="Open command palette (⌘K)"
    >
      <Search className="w-3.5 h-3.5" aria-hidden="true" />
      <span className="font-medium hidden sm:inline">Search</span>
      <kbd className="font-mono text-[9px] text-faint px-1.5 py-0.5 rounded-sm border border-border bg-background" aria-hidden="true">⌘K</kbd>
    </button>
  );
}

// ─── Command Palette (single implementation, audit X3) ───────────────────────

function CommandMenu() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(prev => !prev);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  const run = useCallback((fn: () => void) => {
    setOpen(false);
    fn();
  }, []);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search runs, jobs, applications, metrics…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {ALL_NAV_ITEMS.map(item => (
            <CommandItem key={item.path} onSelect={() => run(() => navigate(item.path))}>
              <item.icon className="mr-2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <span>{item.name}</span>
            </CommandItem>
          ))}
          {EXTRA_NAV.map(extra => (
            <CommandItem key={extra.path} onSelect={() => run(() => navigate(extra.path))}>
              <Settings className="mr-2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <span>{extra.name}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

// ─── Layout ──────────────────────────────────────────────────────────────────

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:left-3 focus:top-3 focus:bg-surface focus:border focus:border-borderStrong focus:px-3 focus:py-2 focus:rounded-sm focus:text-[13px]"
      >
        Skip to main content
      </a>
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Topbar />
        <main className="flex-1 overflow-auto relative p-5 lg:p-7" id="main-content" tabIndex={-1}>
          <div className="max-w-7xl mx-auto w-full h-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { theme } = usePreferences();
  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove('light', 'dark');
    root.classList.add(theme);
  }, [theme]);
  return <>{children}</>;
}

// ─── App ──────────────────────────────────────────────────────────────────────

function App() {
  return (
    <GlobalErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <Router>
            <CommandMenu />
            <Layout>
              <Routes>
                <Route path="/"              element={<Dashboard />} />
                <Route path="/jobs"          element={<Jobs />} />
                <Route path="/pipeline"      element={<Pipeline />} />
                <Route path="/runs"          element={<Runs />} />
                <Route path="/ledger"        element={<Ledger />} />
                <Route path="/applications"  element={<Applications />} />
                <Route path="/intelligence"  element={<Intelligence />} />
                <Route path="/explorer"      element={<Explorer />} />
                <Route path="/metrics"       element={<Metrics />} />
                <Route path="/audit"         element={<Audit />} />
                <Route path="/config"        element={<Configuration />} />
                <Route path="/logs"          element={<Logs />} />
                <Route path="/providers"     element={<Providers />} />
                <Route path="/system"        element={<System />} />
                <Route path="/developer"     element={<Developer />} />
                <Route path="/about"         element={<About />} />
                <Route path="/copilot/inbox" element={<CopilotInbox />} />
                <Route path="/copilot/apply/:id" element={<CopilotApply />} />
                <Route path="/copilot/brief/:id" element={<CopilotBrief />} />
                <Route path="/copilot/assistant/:sessionId" element={<CopilotAssistant />} />
                <Route path="/copilot/history" element={<CopilotHistory />} />
                <Route path="/copilot/analytics" element={<CopilotAnalytics />} />
                <Route path="/copilot/learning" element={<CopilotLearning />} />
                <Route path="/copilot/settings" element={<CopilotSettings />} />
              </Routes>
            </Layout>
            <Toaster />
          </Router>
        </ThemeProvider>
      </QueryClientProvider>
    </GlobalErrorBoundary>
  );
}

export default App;
