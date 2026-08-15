import { useState, useMemo } from 'react';
import { useRuns } from '@/lib/hooks';
import {
  Table, TableBody, TableCell, TableHeader, TableRow,
} from '@/components/ui/table';
import { StatusBadge } from '@/components/operations/StatusBadge';
import { StatRow } from '@/components/operations/StatRow';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { EmptyState } from '@/components/operations/EmptyState';
import { RelativeTime } from '@/components/RelativeTime';
import { cn } from '@/lib/utils';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { CopyButton } from '@/components/CopyButton';
import { ExternalLink, Database } from 'lucide-react';
import { useSortable, sortData } from '@/hooks/useSortable';
import { SortableHeader } from '@/components/SortableHeader';

const RUNS_SORT_TYPES = {
  started_at: 'date' as const,
  status: 'status' as const,
  mode: 'text' as const,
  acquired: 'number' as const,
  classified: 'number' as const,
  submitted: 'number' as const,
  failed: 'number' as const,
};

export default function Runs() {
  const { data: runs = [], isLoading } = useRuns();
  const [selectedRun, setSelectedRun] = useState<any | null>(null);
  const { sort, handleSort } = useSortable(RUNS_SORT_TYPES);

  const runsArray = runs as any[];
  const sortedRuns = useMemo(
    () => sortData(runsArray, sort, RUNS_SORT_TYPES),
    [runsArray, sort],
  );

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        coordinate="01 · 03"
        title="Execution History"
        subtitle={`Audit and inspect past pipeline executions. ${runsArray.length} runs available.`}
      />

      {isLoading ? (
        <GridSkeleton rows={6} className="flex-1" />
      ) : (
        <div className="flex-1 bg-surface border border-border rounded-md overflow-hidden flex flex-col">
        <ScrollArea className="flex-1">
          <Table>
            <TableHeader className="bg-muted/30 sticky top-0 z-10">
              <TableRow className="hover:bg-transparent border-b border-border">
                <SortableHeader column="started_at" label="Started" sort={sort} onSort={handleSort} />
                <SortableHeader column="status" label="Status" sort={sort} onSort={handleSort} />
                <SortableHeader column="mode" label="Mode" sort={sort} onSort={handleSort} />
                <SortableHeader column="acquired" label="Acquired" sort={sort} onSort={handleSort} align="right" />
                <SortableHeader column="classified" label="Classified" sort={sort} onSort={handleSort} align="right" />
                <SortableHeader column="submitted" label="Submitted" sort={sort} onSort={handleSort} align="right" />
                <SortableHeader column="failed" label="Failed" sort={sort} onSort={handleSort} align="right" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedRuns.length ? (
                sortedRuns.map((run: any) => (
                  <TableRow
                    key={run.run_id}
                    tabIndex={0}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedRun(run); } }}
                    className="cursor-pointer hover:bg-muted/30 transition-colors border-b border-border/50 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                    onClick={() => setSelectedRun(run)}
                  >
                    <TableCell className="font-mono text-[11px] text-foreground">
                      <RelativeTime date={run.started_at} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={run.status?.toLowerCase() === 'success' || run.status?.toLowerCase() === 'completed' ? 'success' : run.status?.toLowerCase() === 'failed' ? 'error' : 'warning'} label={run.status ?? 'UNKNOWN'} />
                    </TableCell>
                    <TableCell>
                      <span className={cn(
                        'font-mono text-[9px] font-bold px-1.5 py-0.5 rounded tracking-widest',
                        run.dry_run
                          ? 'bg-muted text-muted-foreground border border-border'
                          : 'bg-healthy/10 text-healthy border border-healthy/40'
                      )}>
                        {run.dry_run ? 'DRY' : 'LIVE'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums text-muted-foreground group-hover:text-foreground transition-colors">{run.acquired ?? 0}</TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums text-muted-foreground group-hover:text-foreground transition-colors">{run.classified ?? 0}</TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums text-healthy font-semibold">{run.submitted ?? 0}</TableCell>
                    <TableCell className={`text-right font-mono text-xs tabular-nums ${run.failed > 0 ? 'text-failed font-semibold' : 'text-muted-foreground'}`}>
                      {run.failed ?? 0}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={7} className="h-32">
                    <EmptyState title="No runs found" description="Launch the pipeline to get started." />
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </ScrollArea>
      </div>
      )}

      <Sheet open={!!selectedRun} onOpenChange={open => !open && setSelectedRun(null)}>
        <SheetContent className="w-[480px] sm:w-[540px] flex flex-col p-0 border-l border-border bg-surface">
          <SheetHeader className="px-6 py-5 border-b border-border bg-surface/80">
            <div className="flex items-center justify-between">
              <SheetTitle className="text-base font-semibold tracking-tight text-foreground">Run Details</SheetTitle>
              {selectedRun && <CopyButton value={selectedRun.run_id} className="h-8 w-8 text-muted-foreground hover:text-foreground" />}
            </div>
            <p className="text-[11px] font-mono text-muted-foreground mt-1 truncate tracking-tight">
              {selectedRun?.run_id}
            </p>
          </SheetHeader>
          <ScrollArea className="flex-1">
            {selectedRun && (
              <div className="px-6 py-6 space-y-8">
                {/* Outcomes */}
                <div>
                  <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3 flex items-center gap-2">
                    <Database className="w-3.5 h-3.5" />
                    Metrics
                  </h3>
                  <div className="bg-surface border border-border rounded-md p-4">
                    <StatRow label="Started"   value={<span className="font-mono"><RelativeTime date={selectedRun.started_at} /></span>} />
                    <StatRow label="Status"    value={<StatusBadge status={selectedRun.status?.toLowerCase() === 'success' || selectedRun.status?.toLowerCase() === 'completed' ? 'success' : selectedRun.status?.toLowerCase() === 'failed' ? 'error' : 'warning'} label={selectedRun.status} />} />
                    <StatRow label="Mode"      value={selectedRun.dry_run ? 'Dry Run' : 'Live Operations'} valueClassName={!selectedRun.dry_run ? 'text-healthy' : ''} />
                    <StatRow label="Acquired"  value={<span className="font-mono">{selectedRun.acquired ?? 0}</span>} />
                    <StatRow label="Classified"value={<span className="font-mono">{selectedRun.classified ?? 0}</span>} />
                    <StatRow label="Selected"  value={<span className="font-mono">{selectedRun.selected ?? 0}</span>} />
                    <StatRow label="Submitted" value={<span className="font-mono text-healthy">{selectedRun.submitted ?? 0}</span>} />
                    <StatRow label="Failed"    value={<span className={`font-mono ${selectedRun.failed > 0 ? 'text-failed' : ''}`}>{selectedRun.failed ?? 0}</span>} />
                  </div>
                </div>

                {/* Cache Performance */}
                {selectedRun.cache_metrics && Object.keys(selectedRun.cache_metrics).length > 0 && (
                  <div>
                    <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3 flex items-center gap-2">
                      <Database className="w-3.5 h-3.5" />
                      Cache Efficiency
                    </h3>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      {[
                        { label: 'LLM',       hits: selectedRun.cache_metrics.llm_hits,       misses: selectedRun.cache_metrics.llm_misses       },
                        { label: 'Embedding', hits: selectedRun.cache_metrics.embedding_hits,  misses: selectedRun.cache_metrics.embedding_misses  },
                        { label: 'Detail',    hits: selectedRun.cache_metrics.detail_hits,     misses: selectedRun.cache_metrics.detail_misses     },
                        { label: 'HTTP',      hits: selectedRun.cache_metrics.http_hits,       misses: selectedRun.cache_metrics.http_misses       },
                      ].map(c => {
                        const total = (c.hits ?? 0) + (c.misses ?? 0);
                        const rate  = total > 0 ? Math.round(((c.hits ?? 0) / total) * 100) : 0;
                        return (
                          <div key={c.label} className="bg-surface border border-border rounded p-3">
                            <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">{c.label}</p>
                            <p className="text-xs font-mono text-foreground mb-0.5">{c.hits ?? 0} <span className="text-muted-foreground">hits</span> / {c.misses ?? 0} <span className="text-muted-foreground">miss</span></p>
                            <p className={`text-[10px] font-mono tracking-tight ${rate >= 80 ? 'text-healthy' : 'text-muted-foreground'}`}>{rate}% hit rate</p>
                          </div>
                        );
                      })}
                    </div>
                    <div className="bg-surface border border-border rounded-md p-4">
                      <StatRow
                        label="Lookup Latency"
                        value={<span className="font-mono">{selectedRun.cache_metrics.total_lookup_time_ms?.toFixed(1) ?? '—'}ms</span>}
                      />
                      <StatRow
                        label="Storage Latency"
                        value={<span className="font-mono">{selectedRun.cache_metrics.total_save_time_ms?.toFixed(1) ?? '—'}ms</span>}
                      />
                    </div>
                  </div>
                )}
                
                <div className="pt-6 border-t border-border">
                  <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-3">Deep Links</h3>
                  <div className="flex flex-col gap-2.5">
                    <a href={`/explorer?runId=${selectedRun.run_id}`} className="flex items-center justify-between p-3 rounded-md border border-border bg-surface hover:bg-muted/30 transition-colors group text-sm font-medium">
                      Open in State Explorer
                      <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </a>
                    <a href={`/api/runs/${selectedRun.run_id}/artifacts/zip`} className="flex items-center justify-between p-3 rounded-md border border-border bg-surface hover:bg-muted/30 transition-colors group text-sm font-medium" target="_blank" rel="noopener noreferrer">
                      Download Artifacts Archive
                      <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </a>
                  </div>
                </div>
              </div>
            )}
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </div>
  );
}
