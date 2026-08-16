import { useMemo, useState, useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { transitionQueueJob, moveQueueJob } from '@/lib/api';
import { useJobs, useJobDetails } from '@/lib/hooks';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnResizeMode,
  type RowSelectionState,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  ContextMenu, ContextMenuContent, ContextMenuItem,
  ContextMenuTrigger, ContextMenuSeparator,
  ContextMenuSub, ContextMenuSubTrigger, ContextMenuSubContent,
} from '@/components/ui/context-menu';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuCheckboxItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { StatusBadge } from '@/components/StatusBadge';
import { CopyButton } from '@/components/CopyButton';
import { RelativeTime } from '@/components/RelativeTime';
import { useJobStore } from '@/store/jobs';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { EmptyState } from '@/components/operations/EmptyState';
import { ErrorState } from '@/components/operations/ErrorState';
import {
  Copy, X, Settings2, EyeOff, ExternalLink, CheckCircle,
  SkipForward, FolderOpen, RefreshCw, Filter,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { JobInspectorContent } from '@/components/JobInspector';

// ─── Saved Views ──────────────────────────────────────────────────────────────
// Predefined filter presets — power user feature, zero configuration required.

const SAVED_VIEWS = [
  { id: 'all',        label: 'All Jobs',    filter: '' },
  { id: 'high-score', label: 'High Score',  filter: '__SCORE_HIGH__' },
  { id: 'applied',    label: 'Applied',     filter: 'APPLIED' },
  { id: 'rejected',   label: 'Rejected',    filter: 'REJECTED' },
  { id: 'pending',    label: 'Pending',     filter: 'PENDING' },
  { id: 'dry-run',    label: 'Dry Run',     filter: 'DRY_RUN_SUPPRESSED' },
] as const;

type ViewId = typeof SAVED_VIEWS[number]['id'];

const openExternalUrl = (url: string | undefined) => {
  if (!url) return;
  window.open(url, '_blank', 'noopener,noreferrer');
};

function scoreColor(score: number | null | undefined) {
  if (score == null) return 'text-muted-foreground';
  if (score >= 70) return 'text-healthy';
  if (score >= 40) return 'text-degraded';
  return 'text-failed';
}

// ─── Column human-readable names ──────────────────────────────────────────────
const COLUMN_LABELS: Record<string, string> = {
  select:          'Select',
  company:         'Company',
  title:           'Title',
  provider:        'Provider',
  location:        'Location',
  posting_age:     'Posting Age',
  score:           'Score',
  decision:        'Decision',
  pipeline_stage:  'Pipeline Stage',
  reason:          'Reason',
  resume:          'Resume',
  applied:         'Applied',
  actions:         'Actions',
};

export default function Jobs() {
  const queryClient = useQueryClient();
  const { data: jobs = [], isLoading, isError, refetch, isFetching } = useJobs();

  // Persisted state
  const { sorting, columnVisibility, setSorting, setColumnVisibility } = useJobStore();

  // Local state
  const [globalFilter, setGlobalFilter]       = useState('');
  const [rowSelection, setRowSelection]        = useState<RowSelectionState>({});
  const [selectedJobId, setSelectedJobId]      = useState<string | null>(null);
  const [activeView, setActiveView]            = useState<ViewId>('all');
  const [jsonDialogOpen, setJsonDialogOpen]    = useState(false);
  const [jsonDialogData, setJsonDialogData]    = useState<any>(null);

  // Query for details
  const { data: jobDetails, isLoading: detailsLoading } = useJobDetails(selectedJobId!);

  // Apply saved view filter
  const applyView = useCallback((viewId: ViewId) => {
    setActiveView(viewId);
    const view = SAVED_VIEWS.find(v => v.id === viewId);
    if (!view) return;
    if (viewId === 'all') {
      setGlobalFilter('');
    } else if (viewId === 'high-score') {
      setGlobalFilter(''); // handled via column filter below
    } else {
      setGlobalFilter(view.filter);
    }
  }, []);

  const columns = useMemo(() => [
    {
      id: 'select',
      header: ({ table }: any) => (
        <Checkbox
          checked={table.getIsAllPageRowsSelected()}
          onCheckedChange={v => table.toggleAllPageRowsSelected(!!v)}
          aria-label="Select all rows"
        />
      ),
      cell: ({ row }: any) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={v => row.toggleSelected(!!v)}
          aria-label="Select row"
          onClick={e => e.stopPropagation()}
        />
      ),
      size: 40,
      enableSorting: false,
      enableResizing: false,
    },
    {
      accessorKey: 'company',
      header: 'Company',
      size: 130,
      cell: ({ row }: any) => <span className="truncate block" title={row.getValue('company')}>{row.getValue('company')}</span>,
    },
    {
      accessorKey: 'title',
      header: 'Title',
      size: 200,
      cell: ({ row }: any) => <span className="truncate block font-medium" title={row.getValue('title')}>{row.getValue('title')}</span>,
    },
    {
      accessorKey: 'provider',
      header: 'Provider',
      size: 100,
      cell: ({ row }: any) => <span className="font-mono text-[10px] text-muted-foreground">{row.getValue('provider') ?? row.original.source}</span>,
    },
    {
      accessorKey: 'location',
      header: 'Location',
      size: 120,
      cell: ({ row }: any) => <span className="truncate block text-muted-foreground text-xs" title={row.getValue('location')}>{row.getValue('location') ?? '—'}</span>,
    },
    {
      accessorKey: 'posting_age',
      header: 'Age',
      size: 60,
      cell: ({ row }: any) => <span className="text-xs text-muted-foreground">{row.getValue('posting_age') ?? '—'}</span>,
    },
    {
      accessorKey: 'score',
      header: 'Score',
      size: 60,
      cell: ({ row }: any) => {
        const s = row.getValue('score') as number | null;
        if (activeView === 'high-score' && s != null && s < 70) return null;
        return <span className={cn('font-mono font-semibold text-xs tabular-nums', scoreColor(s))}>{s ?? '—'}</span>;
      },
    },
    {
      accessorKey: 'decision',
      header: 'Decision',
      size: 100,
      cell: ({ row }: any) => <StatusBadge status={row.getValue('decision') ?? row.original.status ?? 'UNKNOWN'} />,
    },
    {
      accessorKey: 'pipeline_stage',
      header: 'Stage',
      size: 100,
      cell: ({ row }: any) => <span className="text-xs font-medium text-muted-foreground uppercase">{row.getValue('pipeline_stage') ?? '—'}</span>,
    },
    {
      accessorKey: 'reason',
      header: 'Reason',
      size: 150,
      cell: ({ row }: any) => <span className="truncate block text-[10px] text-muted-foreground" title={row.getValue('reason')}>{row.getValue('reason') ?? '—'}</span>,
    },
    {
      accessorKey: 'resume',
      header: 'Resume',
      size: 100,
      cell: ({ row }: any) => <span className="truncate block text-[10px] text-muted-foreground">{row.getValue('resume') ?? '—'}</span>,
    },
    {
      accessorKey: 'applied',
      header: 'Applied',
      size: 80,
      cell: ({ row }: any) => (
        row.getValue('applied') ? (
          <RelativeTime date={row.getValue('applied')} className="text-muted-foreground text-xs" />
        ) : <span className="text-muted-foreground text-xs">—</span>
      ),
    },
    {
      id: 'actions',
      header: '',
      size: 48,
      enableSorting: false,
      enableResizing: false,
      cell: ({ row }: any) => {
        const url = (row.original as any).apply_url;
        if (!url) return null;
        return (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-muted-foreground hover:text-primary"
            onClick={e => { e.stopPropagation(); openExternalUrl(url); }}
            aria-label="Open job externally"
          >
            <ExternalLink className="h-3 w-3" />
          </Button>
        );
      },
    },
  ], [activeView]);

  // Filter rows for high-score view client-side
  const filteredJobs = useMemo(() => {
    if (activeView === 'high-score') {
      return (jobs as any[]).filter(j => (j.score ?? 0) >= 70);
    }
    return jobs;
  }, [jobs, activeView]);

  const table = useReactTable({
    data: filteredJobs,
    columns,
    state: { sorting, columnVisibility, globalFilter, rowSelection },
    enableRowSelection: true,
    columnResizeMode: 'onChange' as ColumnResizeMode,
    onSortingChange: setSorting as any,
    onColumnVisibilityChange: setColumnVisibility as any,
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const { rows } = table.getRowModel();
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 20,
  });

  // Keyboard navigation within the table
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!selectedJobId || !rows.length) return;
      const currentIndex = rows.findIndex(r => (r.original as any).job_id === selectedJobId);
      if (e.key === 'ArrowDown' && currentIndex < rows.length - 1) {
        e.preventDefault();
        setSelectedJobId((rows[currentIndex + 1].original as any).job_id);
      } else if (e.key === 'ArrowUp' && currentIndex > 0) {
        e.preventDefault();
        setSelectedJobId((rows[currentIndex - 1].original as any).job_id);
      } else if (e.key === 'Escape') {
        setSelectedJobId(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedJobId, rows]);

  const handleBulkAction = async (action: string) => {
    const selectedIds = Object.keys(rowSelection)
      .filter(k => rowSelection[k])
      .map(idx => (rows[idx as any].original as any).job_id);
    if (!selectedIds.length) return;
    for (const jobId of selectedIds) {
      if (action === 'APPLIED' || action === 'REJECTED') {
        await transitionQueueJob(jobId, action, 'Bulk Action');
      } else if (action === 'MANUAL_REVIEW') {
        await moveQueueJob(jobId, 'manual_review');
      } else if (action === 'ATS_QUEUE') {
        await moveQueueJob(jobId, 'external_apply');
      }
    }
    setRowSelection({});
    queryClient.invalidateQueries({ queryKey: ['jobs'] });
  };

  const selectedCount = Object.values(rowSelection).filter(Boolean).length;
  const totalVisible  = rows.length;
  const totalAll      = (jobs as any[]).length;

  return (
    <div className="h-full flex flex-col bg-background text-sm">

      <PageHeader
        coordinate="02 · 01"
        title="Jobs"
        subtitle={
          totalVisible < totalAll
            ? `Review, filter, and manage discovered opportunities. ${totalVisible.toLocaleString()} of ${totalAll.toLocaleString()} shown.`
            : 'Review, filter, and manage discovered opportunities.'
        }
        actions={
          <>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs gap-1.5 text-muted-foreground"
              onClick={() => refetch()}
              disabled={isFetching}
              aria-label="Refresh jobs"
            >
              <RefreshCw className={cn('w-3 h-3', isFetching && 'animate-spin')} />
              Refresh
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1.5">
                  <Settings2 className="h-3 w-3" /> Columns
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44 text-xs">
                {table.getAllLeafColumns()
                  .filter(c => c.id !== 'select' && c.id !== 'actions')
                  .map(column => (
                    <DropdownMenuCheckboxItem
                      key={column.id}
                      checked={column.getIsVisible()}
                      onCheckedChange={v => column.toggleVisibility(!!v)}
                      className="text-xs"
                    >
                      {COLUMN_LABELS[column.id] ?? column.id}
                    </DropdownMenuCheckboxItem>
                  ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        }
      />

      {/* Saved Views + Filter Row */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-border/40 shrink-0 bg-background/80 px-4">
        {/* Saved view tabs */}
        <Tabs value={activeView} onValueChange={v => applyView(v as ViewId)} className="mr-4 min-w-0 max-w-full">
          <TabsList className="border-0 gap-0 flex-wrap max-w-full">
            {SAVED_VIEWS.map(view => (
              <TabsTrigger
                key={view.id}
                value={view.id}
                className="px-3 py-2.5 text-xs whitespace-nowrap"
              >
                {view.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {/* Bulk actions when rows selected */}
        {selectedCount > 0 && (
          <div className="flex items-center gap-2 py-1.5 ml-2 border-l border-border/40 pl-4">
            <span className="text-xs font-medium text-muted-foreground">{selectedCount} selected</span>
            <Button variant="outline" size="sm" className="h-7 text-xs text-healthy border-healthy/40 hover:bg-healthy/10" onClick={() => handleBulkAction('APPLIED')}>
              <CheckCircle className="w-3 h-3 mr-1" /> Mark Applied
            </Button>
            <Button variant="outline" size="sm" className="h-7 text-xs text-failed border-failed/40 hover:bg-failed/10" onClick={() => handleBulkAction('REJECTED')}>
              <SkipForward className="w-3 h-3 mr-1" /> Reject
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-7 text-xs">
                  <FolderOpen className="w-3 h-3 mr-1" /> Move To
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="text-xs">
                <DropdownMenuItem onSelect={() => handleBulkAction('MANUAL_REVIEW')}>Manual Review</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => handleBulkAction('ATS_QUEUE')}>ATS Queue</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground" onClick={() => setRowSelection({})}>
              <X className="w-3 h-3 mr-1" /> Clear
            </Button>
          </div>
        )}

        {/* Search — pushes to the right */}
        <div className="flex items-center gap-2 ml-auto py-1.5 min-w-0 flex-1 sm:flex-none">
          <Filter className="w-3 h-3 text-muted-foreground" />
          <Input
            placeholder="Filter…"
            aria-label="Filter jobs"
            value={globalFilter ?? ''}
            onChange={e => setGlobalFilter(e.target.value)}
            className="h-7 w-52 text-xs bg-transparent border-0 focus-visible:ring-0 p-0 placeholder:text-muted-foreground/50"
          />
        </div>
      </div>

      {/* Main content: table + detail panel */}
      <div className="flex-1 overflow-hidden">
        <ResizablePanelGroup direction="horizontal">
          {/* Data Grid */}
          <ResizablePanel defaultSize={selectedJobId ? 58 : 100} minSize={30} className="relative flex flex-col bg-surface min-w-0 overflow-hidden">
            <div ref={parentRef} className="flex-1 overflow-auto relative min-w-0">
              {isError ? (
                <div className="p-4">
                  <ErrorState message="Job data could not be loaded." onRetry={() => refetch()} />
                </div>
              ) : rows.length === 0 && !isLoading ? (
                <EmptyState
                  title="No jobs match this filter"
                  description="Try adjusting the filter or switching views."
                  action={
                    <Button variant="ghost" size="sm" className="mt-4 text-xs" onClick={() => { setGlobalFilter(''); setActiveView('all'); }}>
                      Clear filter
                    </Button>
                  }
                />
              ) : (
                <div style={{ height: `${virtualizer.getTotalSize()}px`, width: table.getTotalSize(), position: 'relative' }}>
                  {/* Sticky header */}
                  <div className="sticky top-0 z-20 bg-background border-b border-border/40 flex font-mono text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    {table.getHeaderGroups().map(hg => (
                      <div key={hg.id} className="flex w-full">
                        {hg.headers.map(header => (
                          <div
                            key={header.id}
                            style={{ width: header.getSize() }}
                            className={cn(
                              'flex items-center px-3 py-2 group select-none',
                              header.id === 'select' && 'sticky left-0 bg-background z-30',
                            )}
                          >
                            <div
                              className="flex-1 truncate cursor-pointer"
                              onClick={header.column.getToggleSortingHandler()}
                              title={COLUMN_LABELS[header.id] ?? header.id}
                            >
                              {flexRender(header.column.columnDef.header, header.getContext())}
                              {{ asc: ' ↑', desc: ' ↓' }[header.column.getIsSorted() as string] ?? null}
                            </div>
                            {header.column.getCanResize() && (
                              <div
                                onMouseDown={header.getResizeHandler()}
                                onTouchStart={header.getResizeHandler()}
                                className={cn(
                                  'absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary/40 transition-colors',
                                  header.column.getIsResizing() && 'bg-primary',
                                )}
                              />
                            )}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>

                  {/* Virtualised rows */}
                  {virtualizer.getVirtualItems().map(virtualRow => {
                    const row = rows[virtualRow.index];
                    const isSelected = (row.original as any).job_id === selectedJobId;
                    const isChecked  = row.getIsSelected();

                    return (
                      <ContextMenu key={row.id}>
                        <ContextMenuTrigger asChild>
                          <div
                            style={{
                              position: 'absolute',
                              top: 0, left: 0,
                              width: '100%',
                              height: `${virtualRow.size}px`,
                              transform: `translateY(${virtualRow.start}px)`,
                            }}
                            role="row"
                            aria-selected={isSelected}
                            tabIndex={0}
                            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedJobId((row.original as any).job_id); } }}
                            className={cn(
                              'flex border-b border-border/20 transition-colors cursor-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
                              isSelected  ? 'bg-secondary'  : 'hover:bg-muted/50',
                              isChecked   ? 'bg-muted'   : '',
                            )}
                            onClick={() => setSelectedJobId((row.original as any).job_id)}
                          >
                            {row.getVisibleCells().map(cell => (
                              <div
                                key={cell.id}
                                style={{ width: cell.column.getSize() }}
                                className={cn(
                                  'flex items-center px-3 overflow-hidden',
                                  cell.column.id === 'select' && 'sticky left-0 bg-inherit z-10',
                                )}
                              >
                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                              </div>
                            ))}
                          </div>
                        </ContextMenuTrigger>

                        <ContextMenuContent className="w-52 text-xs">
                          <ContextMenuItem onClick={() => navigator.clipboard.writeText((row.original as any).job_id)}>
                            <Copy className="w-3 h-3 mr-2" /> Copy Job ID
                          </ContextMenuItem>
                          <ContextMenuItem onClick={() => openExternalUrl((row.original as any).apply_url)}>
                            <ExternalLink className="w-3 h-3 mr-2" /> Open Externally
                          </ContextMenuItem>
                          <ContextMenuSeparator />
                          <ContextMenuSub>
                            <ContextMenuSubTrigger>Change Status</ContextMenuSubTrigger>
                            <ContextMenuSubContent className="w-36">
                              {['APPLIED', 'REJECTED', 'OPENED'].map(s => (
                                <ContextMenuItem
                                  key={s}
                                  onSelect={() => {
                                    transitionQueueJob((row.original as any).job_id, s, 'Context Menu');
                                    queryClient.invalidateQueries({ queryKey: ['jobs'] });
                                  }}
                                >
                                  Set {s}
                                </ContextMenuItem>
                              ))}
                            </ContextMenuSubContent>
                          </ContextMenuSub>
                          <ContextMenuSub>
                            <ContextMenuSubTrigger>Move to Queue</ContextMenuSubTrigger>
                            <ContextMenuSubContent className="w-40">
                              <ContextMenuItem onSelect={() => { moveQueueJob((row.original as any).job_id, 'manual_review'); queryClient.invalidateQueries({ queryKey: ['jobs'] }); }}>
                                Manual Review
                              </ContextMenuItem>
                              <ContextMenuItem onSelect={() => { moveQueueJob((row.original as any).job_id, 'external_apply'); queryClient.invalidateQueries({ queryKey: ['jobs'] }); }}>
                                ATS Queue
                              </ContextMenuItem>
                            </ContextMenuSubContent>
                          </ContextMenuSub>
                          <ContextMenuSeparator />
                          <ContextMenuItem className="text-muted-foreground">
                            <EyeOff className="w-3 h-3 mr-2" /> Hide Job
                          </ContextMenuItem>
                        </ContextMenuContent>
                      </ContextMenu>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Loading state — initial load */}
            {isLoading && rows.length === 0 && (
              <div className="absolute inset-0 z-40">
                <GridSkeleton rows={6} className="h-full border-0" />
              </div>
            )}
          </ResizablePanel>

          {/* Detail Panel */}
          {selectedJobId && (
            <>
              <ResizableHandle withHandle className="bg-border/50 hover:bg-primary/30 transition-colors w-1" />
              <ResizablePanel
                defaultSize={42}
                minSize={28}
                maxSize={58}
                className="bg-surface border-l border-border/50 flex flex-col relative z-20"
              >
                {/* Detail Header */}
                <div className="h-11 border-b border-border/40 flex items-center justify-between px-4 bg-secondary/20 shrink-0">
                  <span className="font-mono text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Job Details</span>
                  <div className="flex items-center gap-1">
                    <CopyButton value={selectedJobId} />
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setSelectedJobId(null)} aria-label="Close detail panel">
                      <X className="w-3 h-3" />
                    </Button>
                  </div>
                </div>

                <div className="flex-1 min-h-0">
                  {detailsLoading ? (
                    <GridSkeleton rows={5} className="m-4" />
                  ) : jobDetails ? (
                    <JobInspectorContent
                      data={jobDetails}
                      jobId={selectedJobId}
                      variant="jobs"
                      onOpenJson={() => { setJsonDialogData(jobDetails); setJsonDialogOpen(true); }}
                      onTransitioned={() => queryClient.invalidateQueries({ queryKey: ['jobs'] })}
                    />
                  ) : (
                    <div className="p-6 text-center text-sm text-muted-foreground">
                      Failed to load job details.
                    </div>
                  )}
                </div>
              </ResizablePanel>
            </>
          )}
        </ResizablePanelGroup>
      </div>

      {/* JSON viewer dialog */}
      <Dialog open={jsonDialogOpen} onOpenChange={setJsonDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle className="text-sm">Job Data</DialogTitle>
          </DialogHeader>
          <pre className="text-[11px] font-mono bg-console text-console-foreground/75 p-4 rounded-md overflow-auto leading-relaxed">
            {JSON.stringify(jsonDialogData, null, 2)}
          </pre>
        </DialogContent>
      </Dialog>
    </div>
  );
}
