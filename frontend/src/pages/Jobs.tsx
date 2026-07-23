import { useMemo, useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchJobs, fetchJobDetails, transitionQueueJob, moveQueueJob } from '@/lib/api';
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
import { ScrollArea } from '@/components/ui/scroll-area';
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
import { StatusBadge } from '@/components/StatusBadge';
import { CopyButton } from '@/components/CopyButton';
import { RelativeTime } from '@/components/RelativeTime';
import { useJobStore } from '@/store/jobs';
import {
  Copy, X, Settings2, EyeOff, ExternalLink, CheckCircle,
  SkipForward, FolderOpen, RefreshCw, Filter,
} from 'lucide-react';
import { cn } from '@/lib/utils';

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
  if (score >= 70) return 'text-emerald-500';
  if (score >= 40) return 'text-amber-500';
  return 'text-red-400';
}

// ─── Column human-readable names ──────────────────────────────────────────────
const COLUMN_LABELS: Record<string, string> = {
  select:          'Select',
  status:          'Status',
  company:         'Company',
  title:           'Title',
  score:           'AI Score',
  location:        'Location',
  source:          'Source',
  last_updated_at: 'Last Updated',
  actions:         'Actions',
};

export default function Jobs() {
  const queryClient = useQueryClient();
  const { data: jobs = [], isLoading, refetch, isFetching } = useQuery({
    queryKey: ['jobs'],
    queryFn: fetchJobs,
  });

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
  const { data: jobDetails, isLoading: detailsLoading } = useQuery({
    queryKey: ['job', selectedJobId],
    queryFn: () => fetchJobDetails(selectedJobId!),
    enabled: !!selectedJobId,
  });

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
      accessorKey: 'status',
      header: 'Status',
      size: 110,
      cell: ({ row }: any) => <StatusBadge status={row.getValue('status') ?? 'UNKNOWN'} />,
    },
    {
      accessorKey: 'company',
      header: 'Company',
      size: 150,
      cell: ({ row }: any) => (
        <span className="truncate block" title={row.getValue('company')}>
          {row.getValue('company')}
        </span>
      ),
    },
    {
      accessorKey: 'title',
      header: 'Title',
      size: 260,
      cell: ({ row }: any) => (
        <span className="truncate block" title={row.getValue('title')}>
          {row.getValue('title')}
        </span>
      ),
    },
    {
      accessorKey: 'score',
      header: 'Score',
      size: 72,
      cell: ({ row }: any) => {
        const s = row.getValue('score') as number | null;
        if (activeView === 'high-score' && s != null && s < 70) return null;
        return (
          <span className={cn('font-mono font-semibold text-xs tabular-nums', scoreColor(s))}>
            {s ?? '—'}
          </span>
        );
      },
    },
    {
      accessorKey: 'location',
      header: 'Location',
      size: 140,
      cell: ({ row }: any) => (
        <span className="truncate block text-muted-foreground" title={row.getValue('location')}>
          {row.getValue('location') ?? '—'}
        </span>
      ),
    },
    {
      accessorKey: 'source',
      header: 'Source',
      size: 110,
      cell: ({ row }: any) => (
        <span className="font-mono text-[10px] text-muted-foreground">{row.getValue('source')}</span>
      ),
    },
    {
      accessorKey: 'last_updated_at',
      header: 'Updated',
      size: 110,
      cell: ({ row }: any) => (
        <RelativeTime date={row.getValue('last_updated_at')} className="text-muted-foreground text-xs" />
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

      {/* Page Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Jobs</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Review, filter, and manage discovered opportunities.
            {totalVisible < totalAll && (
              <span className="ml-1 text-primary font-medium">{totalVisible.toLocaleString()} of {totalAll.toLocaleString()} shown</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
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
        </div>
      </div>

      {/* Saved Views + Filter Row */}
      <div className="flex items-center gap-0 border-b border-border/40 shrink-0 bg-background/80 px-4">
        {/* Saved view tabs */}
        <div className="flex items-center gap-0 mr-4 -mb-px">
          {SAVED_VIEWS.map(view => (
            <button
              key={view.id}
              onClick={() => applyView(view.id)}
              className={cn(
                'px-3 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap',
                activeView === view.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border/50'
              )}
            >
              {view.label}
            </button>
          ))}
        </div>

        {/* Bulk actions when rows selected */}
        {selectedCount > 0 && (
          <div className="flex items-center gap-2 py-1.5 ml-2 border-l border-border/40 pl-4">
            <span className="text-xs font-medium text-muted-foreground">{selectedCount} selected</span>
            <Button variant="outline" size="sm" className="h-7 text-xs text-emerald-600 border-emerald-500/30 hover:bg-emerald-500/10" onClick={() => handleBulkAction('APPLIED')}>
              <CheckCircle className="w-3 h-3 mr-1" /> Mark Applied
            </Button>
            <Button variant="outline" size="sm" className="h-7 text-xs text-red-500 border-red-500/30 hover:bg-red-500/10" onClick={() => handleBulkAction('REJECTED')}>
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
        <div className="flex items-center gap-2 ml-auto py-1.5">
          <Filter className="w-3 h-3 text-muted-foreground" />
          <Input
            placeholder="Filter…"
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
          <ResizablePanel defaultSize={selectedJobId ? 58 : 100} minSize={30} className="relative flex flex-col bg-card">
            <div ref={parentRef} className="flex-1 overflow-auto relative">
              {rows.length === 0 && !isLoading ? (
                <div className="flex flex-col items-center justify-center h-full py-20 text-muted-foreground">
                  <Briefcase className="w-8 h-8 mb-3 opacity-20" />
                  <p className="text-sm font-medium">No jobs match this filter</p>
                  <p className="text-xs mt-1">Try adjusting the filter or switching views</p>
                  <Button variant="ghost" size="sm" className="mt-4 text-xs" onClick={() => { setGlobalFilter(''); setActiveView('all'); }}>
                    Clear filter
                  </Button>
                </div>
              ) : (
                <div style={{ height: `${virtualizer.getTotalSize()}px`, width: table.getTotalSize(), position: 'relative' }}>
                  {/* Sticky header */}
                  <div className="sticky top-0 z-20 bg-background border-b border-border/40 flex text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
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
                            className={cn(
                              'flex border-b border-border/20 transition-colors cursor-default',
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

            {/* Loading overlay */}
            {isLoading && (
              <div className="absolute inset-0 bg-background/60 backdrop-blur-sm flex items-center justify-center z-50">
                <div className="flex items-center gap-2 text-sm text-muted-foreground font-mono bg-card px-4 py-2 border border-border/50 rounded-full shadow-sm">
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  Loading jobs…
                </div>
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
                className="bg-card border-l border-border/50 flex flex-col relative z-20"
              >
                {/* Detail Header */}
                <div className="h-11 border-b border-border/40 flex items-center justify-between px-4 bg-secondary/20 shrink-0">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Job Details</span>
                  <div className="flex items-center gap-1">
                    <CopyButton value={selectedJobId} />
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setSelectedJobId(null)} aria-label="Close detail panel">
                      <X className="w-3 h-3" />
                    </Button>
                  </div>
                </div>

                <ScrollArea className="flex-1">
                  {detailsLoading ? (
                    <div className="p-5 space-y-4 animate-pulse">
                      <div className="h-5 w-3/4 bg-muted rounded" />
                      <div className="h-3 w-1/2 bg-muted rounded" />
                      <div className="h-24 bg-muted rounded" />
                      <div className="grid grid-cols-2 gap-3">
                        {[1,2,3,4].map(i => <div key={i} className="h-12 bg-muted rounded" />)}
                      </div>
                    </div>
                  ) : jobDetails ? (
                    <JobDetailContent
                      jobDetails={jobDetails}
                      selectedJobId={selectedJobId}
                      onOpenJson={() => { setJsonDialogData(jobDetails.overview); setJsonDialogOpen(true); }}
                      queryClient={queryClient}
                    />
                  ) : (
                    <div className="p-6 text-center text-sm text-muted-foreground">
                      Failed to load job details.
                    </div>
                  )}
                </ScrollArea>
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
          <pre className="text-[11px] font-mono bg-muted/40 p-4 rounded-md overflow-auto leading-relaxed">
            {JSON.stringify(jsonDialogData, null, 2)}
          </pre>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Job Detail Content ───────────────────────────────────────────────────────
// Order: Header → AI Assessment → Actions → Metadata → Timeline

function JobDetailContent({
  jobDetails,
  selectedJobId,
  onOpenJson,
  queryClient,
}: {
  jobDetails: any;
  selectedJobId: string;
  onOpenJson: () => void;
  queryClient: any;
}) {
  const ov = jobDetails.overview;

  return (
    <div className="p-5 space-y-5">

      {/* Header */}
      <div>
        <h2 className="text-base font-bold tracking-tight leading-snug">{ov.title}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          <span className="font-medium text-foreground">{ov.company}</span>
          {ov.location && <> · <span>{ov.location}</span></>}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <StatusBadge status={ov.status ?? ov.workflow_status ?? 'UNKNOWN'} />
          {ov.score != null && (
            <span className={cn('text-xs font-mono font-semibold', scoreColor(ov.score))}>
              {ov.score} / 100
            </span>
          )}
        </div>
      </div>

      {/* AI Assessment — elevated to top */}
      {(ov.reasoning || ov.notes || ov.ai_reason) && (
        <div className="bg-primary/5 border border-primary/15 rounded-lg p-4">
          <p className="text-[10px] font-semibold text-primary uppercase tracking-wider mb-2">AI Assessment</p>
          <p className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap">
            {ov.reasoning ?? ov.ai_reason ?? ov.notes}
          </p>
        </div>
      )}

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700 text-white border-0"
          onClick={async () => {
            await transitionQueueJob(selectedJobId, 'APPLIED', 'Manual APPLIED');
            queryClient.invalidateQueries({ queryKey: ['jobs'] });
          }}
        >
          <CheckCircle className="w-3 h-3 mr-1.5" /> Mark Applied
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-8 text-xs text-red-500 border-red-500/30 hover:bg-red-500/10"
          onClick={async () => {
            await transitionQueueJob(selectedJobId, 'REJECTED', 'Manual REJECTED');
            queryClient.invalidateQueries({ queryKey: ['jobs'] });
          }}
        >
          <SkipForward className="w-3 h-3 mr-1.5" /> Reject
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-8 text-xs">
              <FolderOpen className="w-3 h-3 mr-1.5" /> Move To
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="text-xs">
            <DropdownMenuItem onSelect={async () => { await moveQueueJob(selectedJobId, 'manual_review'); queryClient.invalidateQueries({ queryKey: ['jobs'] }); }}>
              Manual Review Queue
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={async () => { await moveQueueJob(selectedJobId, 'external_apply'); queryClient.invalidateQueries({ queryKey: ['jobs'] }); }}>
              ATS Queue
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        {ov.apply_url && (
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => openExternalUrl(ov.apply_url)}>
            <ExternalLink className="w-3 h-3 mr-1.5" /> Open Job
          </Button>
        )}
        <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground" onClick={onOpenJson}>
          View JSON
        </Button>
      </div>

      {/* Metadata Grid */}
      <div className="grid grid-cols-2 gap-3">
        {[
          { label: 'Priority',  value: ov.priority },
          { label: 'Source',    value: ov.source    },
          { label: 'Experience',value: ov.experience },
          { label: 'Posted',    value: ov.posted_date },
        ].filter(m => m.value).map(m => (
          <div key={m.label} className="bg-muted/30 rounded p-3">
            <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">{m.label}</p>
            <p className="text-xs font-medium truncate">{String(m.value)}</p>
          </div>
        ))}
      </div>

      {/* Timeline */}
      {jobDetails.events?.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">Application History</p>
          <div className="space-y-0 relative before:absolute before:left-[5px] before:top-0 before:h-full before:w-px before:bg-border/50">
            {jobDetails.events.map((evt: any) => (
              <div key={evt.id ?? evt.created_at} className="flex gap-3 py-2 pl-4">
                <div className="absolute left-[2px] w-2 h-2 rounded-full bg-border border-2 border-background mt-1 z-10" />
                <div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={evt.status} />
                    <RelativeTime date={evt.created_at} className="text-[10px] text-muted-foreground" />
                  </div>
                  {evt.detail && (
                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{evt.detail}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Inline icon for empty state ──────────────────────────────────────────────
function Briefcase({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
      <line x1="12" y1="12" x2="12" y2="12" />
    </svg>
  );
}
