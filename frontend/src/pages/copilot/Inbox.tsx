import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { createSession } from '@/lib/api/copilot';
import { useBrief, useCopilotOpportunities } from '@/lib/hooks';
import type { CopilotOpportunity } from '@/lib/types/copilot';
import { cn, formatSalary } from '@/lib/utils';
import { useSortable, sortData } from '@/hooks/useSortable';
import { sortIndicator, type SortType } from '@/lib/sort';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet';
import {
  Inbox as InboxIcon, Search, Loader2, CheckCircle, SkipForward, XCircle,
  ExternalLink, AlertTriangle, Brain, RefreshCw, Briefcase, ArrowUpDown, Settings2,
} from 'lucide-react';

// ─── Client-side Skip/Dismiss (backend has no endpoint yet) ─────────────────
// Both Skip and Dismiss hide the row on this browser, persisted in localStorage
// under `copilot.inbox.dismissed` = opportunity_id[]. The server still returns
// these rows; this is intentionally a local triage concern only.

const DISMISSED_KEY = 'copilot.inbox.dismissed';

function readDismissed(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function writeDismissed(ids: string[]) {
  try {
    localStorage.setItem(DISMISSED_KEY, JSON.stringify(ids));
  } catch {
    // localStorage unavailable (private mode) — dismissal is session-only.
  }
}

// ─── Derived display helpers ─────────────────────────────────────────────────

const SORT_TYPES: Record<string, SortType> = {
  title: 'text',
  company: 'text',
  comp_max: 'number',
  status_view: 'status',
};

// No fit-score field on CopilotOpportunity yet (data gap) — effort is derived
// from the application strategy: auto=Low, ats=Medium, manual/unsupported=High.
function effortFor(strategy: string) {
  const s = (strategy || '').toLowerCase();
  if (s === 'auto') return { label: 'Low', cls: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' };
  if (s === 'ats') return { label: 'Medium', cls: 'bg-amber-500/10 text-amber-600 dark:text-amber-400' };
  return { label: 'High', cls: 'bg-red-500/10 text-red-600 dark:text-red-400' };
}

// Risk flag: manual/unsupported strategies or REVIEW status need human eyes.
function isRisky(o: CopilotOpportunity): boolean {
  const s = (o.application_strategy || '').toLowerCase();
  return s === 'manual' || s === 'unsupported' || (o.status_view || '').toUpperCase() === 'REVIEW';
}

function salaryText(o: CopilotOpportunity): string {
  if (o.comp_min == null && o.comp_max == null) return '—';
  return formatSalary(o.comp_min ?? undefined, o.comp_max ?? undefined, o.currency ?? undefined);
}

function verdictClass(cls: string | undefined): string {
  switch ((cls || '').toLowerCase()) {
    case 'success': return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400';
    case 'warning': return 'bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400';
    case 'danger': return 'bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400';
    default: return 'bg-primary/5 border-primary/15 text-foreground/80';
  }
}

function SourceBadge({ source }: { source: string }) {
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-muted/60 text-muted-foreground font-mono text-[10px] font-semibold uppercase tracking-wide whitespace-nowrap">
      {source || 'unknown'}
    </span>
  );
}

// ─── Brief sheet (upgrade of JobDrawer; 07_UI §3.1) ─────────────────────────

interface BriefSheetProps {
  opportunity: CopilotOpportunity | null;
  applying: boolean;
  onApply: () => void;
  onSkip: () => void;
  onDismiss: () => void;
  onOpenChange: (open: boolean) => void;
}

function BriefSheet({ opportunity, applying, onApply, onSkip, onDismiss, onOpenChange }: BriefSheetProps) {
  // useBrief already unwraps the envelope — data is the brief payload directly.
  const { data: brief, isLoading, isError, refetch } = useBrief(opportunity?.opportunity_id ?? '');

  return (
    <Sheet open={!!opportunity} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-[640px] p-0 flex flex-col border-l border-border/50">
        {opportunity && (
          <>
            {/* Header */}
            <SheetHeader className="px-5 pt-5 pb-4 border-b border-border/40 bg-muted/10">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <SheetTitle className="text-base font-bold leading-snug truncate">{opportunity.title}</SheetTitle>
                  <SheetDescription className="text-sm mt-1">
                    <span className="font-medium text-foreground">{opportunity.company}</span>
                    <span className="text-muted-foreground"> · {salaryText(opportunity)}</span>
                  </SheetDescription>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <StatusBadge status={opportunity.status_view ?? 'UNKNOWN'} />
                  {isRisky(opportunity) && (
                    <span title="Manual or unsupported application flow — review before applying">
                      <AlertTriangle
                        className="w-4 h-4 text-amber-500"
                        aria-label="Risk: manual or unsupported application flow"
                      />
                    </span>
                  )}
                </div>
              </div>
            </SheetHeader>

            {/* Actions */}
            <div className="flex flex-wrap gap-2 px-5 py-3 border-b border-border/40">
              <Button
                size="sm"
                className="h-8 text-xs gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white border-0"
                onClick={onApply}
                disabled={applying}
              >
                {applying ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                Apply
              </Button>
              {opportunity.apply_url && (
                <Button
                  variant="outline" size="sm" className="h-8 text-xs gap-1.5"
                  onClick={() => window.open(opportunity.apply_url!, '_blank', 'noopener,noreferrer')}
                >
                  <ExternalLink className="w-3 h-3" /> Open Externally
                </Button>
              )}
              <Button
                variant="outline" size="sm" className="h-8 text-xs gap-1.5 text-amber-500 border-amber-500/30 hover:bg-amber-500/10"
                onClick={onSkip}
              >
                <SkipForward className="w-3 h-3" /> Skip
              </Button>
              <Button
                variant="ghost" size="sm" className="h-8 text-xs gap-1.5 text-destructive hover:bg-destructive/10"
                onClick={onDismiss}
              >
                <XCircle className="w-3 h-3" /> Dismiss
              </Button>
            </div>

            {/* Brief body */}
            <ScrollArea className="flex-1">
              {isLoading ? (
                <div className="flex h-48 items-center justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : isError || !brief ? (
                <div className="flex flex-col items-center justify-center h-48 gap-3 px-6 text-center">
                  <AlertTriangle className="w-6 h-6 text-destructive" />
                  <p className="text-xs text-muted-foreground">Failed to load the brief for this opportunity.</p>
                  <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => refetch()}>
                    <RefreshCw className="w-3 h-3 mr-1.5" /> Retry
                  </Button>
                </div>
              ) : (
                <div className="px-5 py-4 space-y-4">
                  {brief.verdict?.label && (
                    <div className={cn('rounded-lg border px-3 py-2.5 text-xs font-medium', verdictClass(brief.verdict.class))}>
                      {brief.verdict.label}
                    </div>
                  )}
                  {brief.sections.map(section => (
                    <div key={section.key} className="bg-muted/20 border border-border/30 rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{section.title}</p>
                        {section.llm_augmented && (
                          <span className="inline-flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wide text-primary bg-primary/10 rounded px-1.5 py-0.5">
                            <Brain className="w-2.5 h-2.5" /> LLM
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap">{section.content}</p>
                      {section.provenance && (
                        <p className="text-[9px] font-mono text-muted-foreground/70 mt-2">{section.provenance}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

// ─── Inbox page ──────────────────────────────────────────────────────────────

export default function Inbox() {
  const navigate = useNavigate();

  // Toolbar state
  const [searchInput, setSearchInput] = useState('');
  const [q, setQ] = useState('');                       // debounced search
  const [sourceFilter, setSourceFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const { sort, handleSort } = useSortable(SORT_TYPES);

  // Row state
  const [dismissed, setDismissed] = useState<string[]>(readDismissed);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [briefId, setBriefId] = useState<string | null>(null);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const parentRef = useRef<HTMLDivElement>(null);

  // Debounce search before it hits the server (30s poll + keystrokes).
  useEffect(() => {
    const t = setTimeout(() => setQ(searchInput.trim()), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const params = useMemo(() => ({
    q: q || undefined,
    source: sourceFilter || undefined,
    status: statusFilter || undefined,
    limit: 500,
  }), [q, sourceFilter, statusFilter]);

  const query = useCopilotOpportunities(params);
  const opps = useMemo(() => query.data?.data ?? [], [query.data]);

  const dismiss = useCallback((id: string) => {
    setDismissed(prev => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      writeDismissed(next);
      return next;
    });
  }, []);

  const handleApply = useCallback(async (opp: CopilotOpportunity) => {
    if (applyingId) return;
    setApplyingId(opp.opportunity_id);
    setActionError(null);
    try {
      const res = await createSession({ opportunity_id: opp.opportunity_id });
      if (res.ok && res.data?.session_id) {
        // Stash the session so the workspace (/copilot/apply/:id) can resume it.
        sessionStorage.setItem(`copilot.session.${opp.opportunity_id}`, res.data.session_id);
      }
      navigate(`/copilot/apply/${opp.opportunity_id}`);
    } catch (err) {
      console.error(err);
      setActionError('Could not start an application session for this opportunity.');
    } finally {
      setApplyingId(null);
    }
  }, [applyingId, navigate]);

  // Skip and Dismiss share the same local persistence for now.
  const handleSkip = useCallback((opp: CopilotOpportunity) => {
    dismiss(opp.opportunity_id);
    setBriefId(cur => (cur === opp.opportunity_id ? null : cur));
    setSelectedId(cur => (cur === opp.opportunity_id ? null : cur));
  }, [dismiss]);
  const handleDismiss = handleSkip;

  const clearFilters = useCallback(() => {
    setSearchInput('');
    setQ('');
    setSourceFilter('');
    setStatusFilter('');
  }, []);

  const clearDismissed = useCallback(() => {
    setDismissed([]);
    writeDismissed([]);
  }, []);

  // Filter/sort pipeline: server fetch → local dismissal → client sort.
  const sourceOptions = useMemo(
    () => [...new Set(opps.map(o => o.source).filter(Boolean))].sort(),
    [opps],
  );
  const statusOptions = useMemo(
    () => [...new Set(opps.map(o => o.status_view).filter((v): v is string => !!v))].sort(),
    [opps],
  );

  const visibleRows = useMemo(
    () => opps.filter(o => !dismissed.includes(o.opportunity_id)),
    [opps, dismissed],
  );
  const rows = useMemo(() => sortData(visibleRows, sort, SORT_TYPES), [visibleRows, sort]);

  const columns = useMemo<ColumnDef<CopilotOpportunity>[]>(() => [
    {
      id: 'title',
      accessorKey: 'title',
      header: 'Title',
      size: 300,
      cell: ({ row }) => {
        const o = row.original;
        const meta = [o.city, o.region, o.country].filter(Boolean).join(', ');
        return (
          <div className="min-w-0 flex-1">
            <div className="font-semibold text-sm text-foreground leading-tight truncate">{o.title}</div>
            {meta && <div className="text-muted-foreground mt-0.5 text-[10px] truncate">{meta}{o.remote ? ' · Remote' : ''}</div>}
          </div>
        );
      },
    },
    {
      id: 'company',
      accessorKey: 'company',
      header: 'Company',
      size: 170,
      cell: ({ row }) => (
        <span className="truncate block text-sm text-muted-foreground" title={row.original.company}>{row.original.company}</span>
      ),
    },
    {
      id: 'source',
      accessorKey: 'source',
      header: 'Source',
      size: 96,
      enableSorting: false,
      cell: ({ row }) => <SourceBadge source={row.original.source} />,
    },
    {
      id: 'comp_max',
      accessorFn: o => o.comp_max,
      header: 'Salary',
      size: 128,
      cell: ({ row }) => <span className="text-xs text-muted-foreground whitespace-nowrap">{salaryText(row.original)}</span>,
    },
    {
      id: 'effort',
      accessorFn: o => effortFor(o.application_strategy).label,
      header: 'Effort',
      size: 84,
      enableSorting: false,
      cell: ({ row }) => {
        const e = effortFor(row.original.application_strategy);
        return (
          <span className={cn('inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide', e.cls)}>
            {e.label}
          </span>
        );
      },
    },
    {
      id: 'status_view',
      accessorKey: 'status_view',
      header: 'Status',
      size: 110,
      cell: ({ row }) => <StatusBadge status={row.original.status_view ?? 'UNKNOWN'} />,
    },
    {
      id: 'risk',
      accessorFn: o => (isRisky(o) ? 1 : 0),
      header: '',
      size: 36,
      enableSorting: false,
      cell: ({ row }) =>
        isRisky(row.original) ? (
          <span title="Manual or unsupported application flow — review before applying">
            <AlertTriangle
              className="w-3.5 h-3.5 text-amber-500"
              aria-label="Risk: manual or unsupported application flow"
            />
          </span>
        ) : null,
    },
    {
      id: 'actions',
      header: '',
      size: 116,
      enableSorting: false,
      cell: ({ row }) => {
        const o = row.original;
        const applying = applyingId === o.opportunity_id;
        return (
          <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
            <Button
              variant="ghost" size="icon"
              className="h-6 w-6 text-emerald-600 hover:bg-emerald-500/10"
              title="Apply (a)"
              aria-label={`Apply to ${o.title}`}
              aria-keyshortcuts="a"
              disabled={applying || !!applyingId}
              onClick={() => void handleApply(o)}
            >
              {applying ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle className="h-3 w-3" />}
            </Button>
            <Button
              variant="ghost" size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-amber-500"
              title="Skip (s)"
              aria-label={`Skip ${o.title}`}
              aria-keyshortcuts="s"
              onClick={() => handleSkip(o)}
            >
              <SkipForward className="h-3 w-3" />
            </Button>
            <Button
              variant="ghost" size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-red-500"
              title="Dismiss (d)"
              aria-label={`Dismiss ${o.title}`}
              aria-keyshortcuts="d"
              onClick={() => handleDismiss(o)}
            >
              <XCircle className="h-3 w-3" />
            </Button>
          </div>
        );
      },
    },
  ], [applyingId, handleApply, handleSkip, handleDismiss]);

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const tableRows = table.getRowModel().rows;

  const virtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
    overscan: 12,
  });

  const briefOpen = !!briefId;
  const briefOpportunity = useMemo(
    () => opps.find(o => o.opportunity_id === briefId) ?? null,
    [opps, briefId],
  );

  // Keyboard: j/k move selection, 1 brief, a apply, s skip, d dismiss.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (briefOpen) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === 'j' || e.key === 'k') {
        e.preventDefault();
        if (!tableRows.length) return;
        const idx = tableRows.findIndex(r => r.original.opportunity_id === selectedId);
        const next = e.key === 'j' ? Math.min(idx + 1, tableRows.length - 1) : Math.max(idx - 1, 0);
        setSelectedId(tableRows[next].original.opportunity_id);
        virtualizer.scrollToIndex(next, { align: 'auto' });
        return;
      }
      if (!selectedId) return;
      const opp = opps.find(o => o.opportunity_id === selectedId);
      if (!opp) return;
      if (e.key === '1') setBriefId(selectedId);
      else if (e.key === 'a') void handleApply(opp);
      else if (e.key === 's') handleSkip(opp);
      else if (e.key === 'd') handleDismiss(opp);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [briefOpen, tableRows, selectedId, opps, handleApply, handleSkip, handleDismiss, virtualizer]);

  const hasActiveFilter = !!(q || sourceFilter || statusFilter);
  const selectRow = useCallback((id: string) => {
    setSelectedId(id);
    setBriefId(id);
  }, []);

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      {/* Page header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <InboxIcon className="w-4 h-4 text-primary" /> Inbox
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Unified triage of every normalized opportunity.
            {rows.length !== opps.length && (
              <span className="ml-1 text-primary font-medium">{rows.length} of {opps.length} shown</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          {query.isFetching ? (
            <Loader2 className="w-3 h-3 animate-spin" aria-label="Refreshing" />
          ) : (
            <span className="w-2 h-2 rounded-full bg-emerald-500/70" aria-hidden="true" />
          )}
          <span>polls every 30s</span>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3 px-6 py-2.5 border-b border-border/40 shrink-0 bg-background/80 flex-wrap">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" aria-hidden="true" />
          <Input
            aria-label="Search opportunities"
            placeholder="Search title, company…"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            className="h-8 w-56 pl-8 text-xs"
          />
        </div>
        <select
          aria-label="Filter by source"
          value={sourceFilter}
          onChange={e => setSourceFilter(e.target.value)}
          className="h-8 rounded-md border border-border/60 bg-background px-2 pr-6 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">All sources</option>
          {sourceOptions.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          aria-label="Filter by status"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="h-8 rounded-md border border-border/60 bg-background px-2 pr-6 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">All statuses</option>
          {statusOptions.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {hasActiveFilter && (
          <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
        <span className="ml-auto text-[10px] text-muted-foreground hidden lg:inline">
          j/k move · 1 brief · a apply · s skip · d dismiss
        </span>
      </div>

      {/* Action error banner */}
      {actionError && (
        <div role="alert" className="flex items-center gap-2 px-6 py-2 border-b border-destructive/20 bg-destructive/5 text-xs text-destructive shrink-0">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>{actionError}</span>
          <button
            type="button"
            className="ml-auto underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
            onClick={() => setActionError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Stale-data error banner (kept when rows are still visible) */}
      {query.isError && rows.length > 0 && (
        <div role="alert" className="flex items-center gap-2 px-6 py-2 border-b border-destructive/20 bg-destructive/5 text-xs text-destructive shrink-0">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>Couldn't refresh opportunities — showing last known data.</span>
          <button
            type="button"
            className="ml-auto underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
            onClick={() => void query.refetch()}
          >
            Retry
          </button>
        </div>
      )}

      {/* Body */}
      <div className="flex-1 overflow-hidden">
        <div ref={parentRef} className="h-full overflow-auto relative">
          {query.isLoading ? (
            <div className="p-6 space-y-3 animate-pulse" aria-busy="true">
              <p className="sr-only" role="status">Loading opportunities…</p>
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className="flex items-center gap-4">
                  <div className="h-4 w-1/3 bg-muted rounded" />
                  <div className="h-4 w-28 bg-muted rounded" />
                  <div className="h-4 w-16 bg-muted rounded" />
                  <div className="h-4 w-24 bg-muted rounded" />
                </div>
              ))}
            </div>
          ) : query.isError && rows.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full py-20 text-center text-muted-foreground px-6">
              <AlertTriangle className="w-8 h-8 mb-3 opacity-40" />
              <p className="text-sm font-medium">Couldn't load opportunities</p>
              <p className="text-xs mt-1 opacity-70 max-w-xs">
                {query.error instanceof Error ? query.error.message : 'Something went wrong while fetching the inbox.'}
              </p>
              <Button variant="outline" size="sm" className="mt-4 h-8 text-xs" onClick={() => void query.refetch()}>
                <RefreshCw className="w-3 h-3 mr-1.5" /> Retry
              </Button>
            </div>
          ) : rows.length === 0 ? (
            hasActiveFilter ? (
              <div className="flex flex-col items-center justify-center h-full py-20 text-center text-muted-foreground px-6">
                <Search className="w-8 h-8 mb-3 opacity-20" />
                <p className="text-sm font-medium">No opportunities match</p>
                <p className="text-xs mt-1 opacity-70">Try adjusting the search or filters.</p>
                <Button variant="ghost" size="sm" className="mt-4 h-8 text-xs" onClick={clearFilters}>
                  Clear filters
                </Button>
              </div>
            ) : dismissed.length > 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-20 text-center text-muted-foreground px-6">
                <CheckCircle className="w-8 h-8 mb-3 opacity-20" />
                <p className="text-sm font-medium">All caught up</p>
                <p className="text-xs mt-1 opacity-70">
                  You've dismissed {dismissed.length} opportunit{dismissed.length === 1 ? 'y' : 'ies'} on this browser.
                </p>
                <Button variant="ghost" size="sm" className="mt-4 h-8 text-xs" onClick={clearDismissed}>
                  Restore dismissed
                </Button>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full py-20 text-center text-muted-foreground px-6">
                <Briefcase className="w-8 h-8 mb-3 opacity-20" />
                <p className="text-sm font-medium">Inbox zero</p>
                <p className="text-xs mt-1 opacity-70">No opportunities yet — ingest a source to start triaging.</p>
                <Button variant="outline" size="sm" className="mt-4 h-8 text-xs" onClick={() => navigate('/copilot/settings')}>
                  <Settings2 className="w-3 h-3 mr-1.5" /> Manage sources
                </Button>
              </div>
            )
          ) : (
            <div
              style={{ height: `${virtualizer.getTotalSize()}px`, width: table.getTotalSize(), position: 'relative' }}
              role="table"
              aria-label="Opportunity inbox"
            >
              {/* Sticky header */}
              <div className="sticky top-0 z-20 bg-background border-b border-border/40 flex text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                {table.getHeaderGroups().map(hg => (
                  <div key={hg.id} className="flex w-full">
                    {hg.headers.map(header => {
                      const id = header.column.id;
                      const sortable = !!SORT_TYPES[id];
                      const active = sort.column === id && sort.direction;
                      return (
                        <div
                          key={header.id}
                          style={{ width: header.getSize() }}
                          role="columnheader"
                          aria-sort={active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
                        >
                          {sortable ? (
                            <button
                              type="button"
                              onClick={() => handleSort(id)}
                              className={cn(
                                'group flex items-center gap-1 w-full px-3 py-2 text-left select-none hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
                                active ? 'text-foreground' : 'cursor-pointer',
                              )}
                            >
                              <span>{header.column.columnDef.header as string}</span>
                              {active
                                ? <span className="text-[10px] font-bold">{sortIndicator(sort.direction)}</span>
                                : <ArrowUpDown className="w-3 h-3 opacity-0 group-hover:opacity-40 transition-opacity" aria-hidden="true" />}
                            </button>
                          ) : (
                            <div className="px-3 py-2">{header.column.columnDef.header as string}</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>

              {/* Virtualized rows */}
              {virtualizer.getVirtualItems().map(virtualRow => {
                const row = tableRows[virtualRow.index];
                const o = row.original;
                const isSelected = selectedId === o.opportunity_id;
                return (
                  <div
                    key={row.id}
                    role="row"
                    aria-selected={isSelected}
                    tabIndex={0}
                    style={{
                      position: 'absolute', top: 0, left: 0, width: '100%',
                      height: `${virtualRow.size}px`, transform: `translateY(${virtualRow.start}px)`,
                    }}
                    className={cn(
                      'flex items-center border-b border-border/20 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
                      isSelected ? 'bg-secondary' : 'hover:bg-muted/50',
                    )}
                    onClick={() => selectRow(o.opportunity_id)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        selectRow(o.opportunity_id);
                      }
                    }}
                  >
                    {row.getVisibleCells().map(cell => (
                      <div
                        key={cell.id}
                        style={{ width: cell.column.getSize() }}
                        className="flex items-center px-3 overflow-hidden h-full"
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <BriefSheet
        opportunity={briefOpportunity}
        applying={applyingId === briefId}
        onApply={() => { if (briefOpportunity) void handleApply(briefOpportunity); }}
        onSkip={() => { if (briefOpportunity) handleSkip(briefOpportunity); }}
        onDismiss={() => { if (briefOpportunity) handleDismiss(briefOpportunity); }}
        onOpenChange={open => { if (!open) setBriefId(null); }}
      />
    </div>
  );
}
