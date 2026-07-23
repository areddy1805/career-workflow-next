import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import {
  LayoutDashboard, Briefcase,
  Play, Inbox, Zap, Server, Search, ChevronRight,
  Settings, PlaySquare, BarChart2, FileJson,
  PanelLeftClose, PanelLeftOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePreferences } from '@/store/preferences';
import { GlobalErrorBoundary } from '@/components/ErrorBoundary';
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput,
  CommandItem, CommandList, CommandSeparator,
} from '@/components/ui/command';
import { fetchManualReviewQueue, fetchExternalApplyQueue } from '@/lib/api';

import Dashboard from '@/pages/Dashboard';
import Jobs from '@/pages/Jobs';
import Runs from '@/pages/Runs';
import Runtime from '@/pages/Runtime';
import Artifacts from '@/pages/Artifacts';
import Analytics from '@/pages/Analytics';
import AppSettings from '@/pages/Settings';
import Pipeline from '@/pages/Pipeline';
import Queues from '@/pages/Queues';
import SearchPage from '@/pages/Search';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
});

// ─── Navigation Structure ─────────────────────────────────────────────────────
// Order: Overview → Jobs → Inbox → Pipeline → Runs → Runtime →
//        Analytics → Search Intelligence → Artifacts → Settings
// ─────────────────────────────────────────────────────────────────────────────

const NAV_GROUPS = [
  {
    label: 'Workspace',
    items: [
      { name: 'Overview',   path: '/',          icon: LayoutDashboard },
      { name: 'Jobs',       path: '/jobs',      icon: Briefcase       },
      { name: 'Inbox',      path: '/queues',    icon: Inbox, badge: true },
    ],
  },
  {
    label: 'Pipeline',
    items: [
      { name: 'Pipeline',   path: '/pipeline',  icon: Play    },
      { name: 'Runs',       path: '/runs',      icon: PlaySquare },
      { name: 'Runtime',    path: '/runtime',   icon: Server  },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { name: 'Analytics',          path: '/analytics', icon: BarChart2 },
      { name: 'Search Intelligence', path: '/search',    icon: Search    },
      { name: 'Artifacts',          path: '/artifacts', icon: FileJson  },
    ],
  },
];

const ALL_NAV_ITEMS = NAV_GROUPS.flatMap(g => g.items);

// ─── Inbox badge count ────────────────────────────────────────────────────────

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

// ─── Sidebar ─────────────────────────────────────────────────────────────────

function Sidebar() {
  const { sidebarOpen, toggleSidebar } = usePreferences();
  const inboxCount = useInboxCount();

  return (
    <div className={cn(
      'border-r border-border/60 bg-card h-screen flex flex-col transition-all duration-200 ease-in-out shrink-0 relative z-40',
      sidebarOpen ? 'w-[220px]' : 'w-[58px]'
    )}>
      {/* Logo */}
      <div className="h-12 border-b border-border/40 flex items-center px-3 shrink-0">
        {sidebarOpen ? (
          <div className="flex items-center gap-2.5 overflow-hidden whitespace-nowrap">
            <div className="w-6 h-6 rounded-md bg-foreground flex items-center justify-center shrink-0">
              <Zap className="w-3.5 h-3.5 text-background" />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-tight leading-none text-foreground">CareerFlow</p>
              <p className="text-[9px] text-muted-foreground font-mono tracking-widest mt-0.5">OPERATIONS</p>
            </div>
          </div>
        ) : (
          <div className="w-6 h-6 rounded-md bg-foreground flex items-center justify-center shrink-0 mx-auto">
            <Zap className="w-3.5 h-3.5 text-background" />
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 flex flex-col gap-3 overflow-y-auto overflow-x-hidden" aria-label="Main navigation">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {sidebarOpen && (
              <p className="text-[9px] font-semibold text-muted-foreground/50 uppercase tracking-widest px-2 mb-1">
                {group.label}
              </p>
            )}
            <div className="flex flex-col gap-0.5">
              {group.items.map(item => (
                <NavItem
                  key={item.path}
                  item={item}
                  collapsed={!sidebarOpen}
                  badge={item.badge ? inboxCount : null}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-2 py-2 border-t border-border/60 flex flex-col gap-0.5">
        <NavLink
          to="/settings"
          title={!sidebarOpen ? 'Settings' : undefined}
          className={({ isActive }) => cn(
            'flex items-center gap-3 px-2.5 py-2 rounded-md text-xs font-medium transition-all duration-150 whitespace-nowrap',
            isActive
              ? 'bg-secondary text-foreground'
              : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground'
          )}
        >
          <Settings className="w-4 h-4 shrink-0" />
          {sidebarOpen && <span>Settings</span>}
        </NavLink>
        <button
          onClick={toggleSidebar}
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          className="flex items-center gap-3 px-2.5 py-2 rounded-md text-xs text-muted-foreground hover:bg-secondary/80 hover:text-foreground transition-all duration-150 whitespace-nowrap"
        >
          {sidebarOpen
            ? <PanelLeftClose className="w-4 h-4 shrink-0" />
            : <PanelLeftOpen className="w-4 h-4 shrink-0" />}
          {sidebarOpen && <span className="text-xs">Collapse</span>}
        </button>
      </div>
    </div>
  );
}

function NavItem({
  item,
  collapsed,
  badge,
}: {
  item: typeof ALL_NAV_ITEMS[0];
  collapsed: boolean;
  badge?: number | null;
}) {
  return (
    <NavLink
      to={item.path}
      end={item.path === '/'}
      title={collapsed ? item.name : undefined}
      className={({ isActive }) => cn(
        'flex items-center gap-3 px-2.5 py-2 rounded-md text-xs font-medium transition-all duration-150 whitespace-nowrap group relative',
        isActive
          ? 'bg-secondary text-foreground'
          : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground'
      )}
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 bg-primary rounded-r-full" aria-hidden="true" />
          )}
          <item.icon className={cn('w-4 h-4 shrink-0', isActive ? 'text-foreground' : 'group-hover:text-foreground')} />
          {!collapsed && <span className="flex-1">{item.name}</span>}
          {!collapsed && badge != null && (
            <span className="ml-auto text-[9px] font-bold bg-muted-foreground/10 text-foreground px-1.5 py-0.5 rounded-full min-w-[18px] text-center leading-none">
              {badge > 99 ? '99+' : badge}
            </span>
          )}
          {collapsed && badge != null && (
            <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 bg-foreground rounded-full" aria-label={`${badge} items`} />
          )}
        </>
      )}
    </NavLink>
  );
}

// ─── Topbar ──────────────────────────────────────────────────────────────────

function Topbar() {
  const location = useLocation();
  const crumbs = buildBreadcrumb(location.pathname);

  return (
    <header
      className="h-11 border-b border-border/40 bg-background flex items-center px-4 justify-between shrink-0 z-30 sticky top-0"
      role="banner"
    >
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb">
        <ol className="flex items-center gap-1 text-xs">
          {crumbs.map((crumb, i) => (
            <li key={crumb.label} className="flex items-center gap-1">
              {i > 0 && <ChevronRight className="w-3 h-3 text-muted-foreground/40" aria-hidden="true" />}
              <span className={cn(
                i === crumbs.length - 1
                  ? 'font-semibold text-foreground'
                  : 'text-muted-foreground/60'
              )}>
                {crumb.label}
              </span>
            </li>
          ))}
        </ol>
      </nav>

      {/* Right side */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground" aria-label="Live data">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 pulse-green" aria-hidden="true" />
          <span className="font-mono">LIVE</span>
        </div>
        <CommandTrigger />
      </div>
    </header>
  );
}

function buildBreadcrumb(pathname: string) {
  const match = [...ALL_NAV_ITEMS, { path: '/settings', name: 'Settings' }]
    .find(i => i.path === pathname || (i.path === '/' && pathname === '/'));
  return [
    { label: 'CareerFlow' },
    { label: match?.name ?? (pathname.slice(1) || 'Overview') },
  ];
}

function CommandTrigger() {
  return (
    <button
      className="flex items-center gap-2 text-xs text-muted-foreground bg-secondary/40 hover:bg-secondary border border-border/40 px-3 py-1.5 rounded-md transition-all duration-150"
      onClick={() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
      aria-label="Open command palette (⌘K)"
    >
      <Search className="w-3 h-3" aria-hidden="true" />
      <span>Search…</span>
      <kbd className="font-mono text-[9px] bg-background px-1.5 py-0.5 rounded border border-border/60 ml-1" aria-hidden="true">⌘K</kbd>
    </button>
  );
}

// ─── Command Palette ──────────────────────────────────────────────────────────

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
      <CommandInput placeholder="Search pages, jobs, runs…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Navigate">
          {ALL_NAV_ITEMS.map(item => (
            <CommandItem key={item.path} onSelect={() => run(() => navigate(item.path))}>
              <item.icon className="mr-2 h-4 w-4 text-muted-foreground" />
              <span>{item.name}</span>
            </CommandItem>
          ))}
          <CommandItem onSelect={() => run(() => navigate('/settings'))}>
            <Settings className="mr-2 h-4 w-4 text-muted-foreground" />
            <span>Settings</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Actions">
          <CommandItem onSelect={() => run(() => navigate('/pipeline'))}>
            <Play className="mr-2 h-4 w-4 text-muted-foreground" />
            <span>Open Pipeline Control</span>
          </CommandItem>
          <CommandItem onSelect={() => run(() => navigate('/queues'))}>
            <Inbox className="mr-2 h-4 w-4 text-muted-foreground" />
            <span>Open Inbox</span>
          </CommandItem>
          <CommandItem onSelect={() => run(() => navigate('/jobs'))}>
            <Briefcase className="mr-2 h-4 w-4 text-muted-foreground" />
            <span>Browse Jobs</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

// ─── Layout ───────────────────────────────────────────────────────────────────

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Topbar />
        <main className="flex-1 overflow-auto relative" id="main-content">
          {children}
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
                <Route path="/"          element={<Dashboard />} />
                <Route path="/jobs"      element={<Jobs />} />
                <Route path="/runs"      element={<Runs />} />
                <Route path="/runtime"   element={<Runtime />} />
                <Route path="/artifacts" element={<Artifacts />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/queues"    element={<Queues />} />
                <Route path="/search"    element={<SearchPage />} />
                <Route path="/settings"  element={<AppSettings />} />
                <Route path="/pipeline"  element={<Pipeline />} />
              </Routes>
            </Layout>
          </Router>
        </ThemeProvider>
      </QueryClientProvider>
    </GlobalErrorBoundary>
  );
}

export default App;
