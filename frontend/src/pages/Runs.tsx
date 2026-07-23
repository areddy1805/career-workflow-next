import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchRuns } from '@/lib/api';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { StatusBadge } from '@/components/StatusBadge';
import { RelativeTime } from '@/components/RelativeTime';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { CopyButton } from '@/components/CopyButton';

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between py-2 border-b border-border/20 last:border-0 text-xs gap-4">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="font-medium text-right truncate">{value}</span>
    </div>
  );
}

export default function Runs() {
  const { data: runs = [], isLoading } = useQuery({
    queryKey: ['runs'],
    queryFn: fetchRuns,
  });

  const [selectedRun, setSelectedRun] = useState<any | null>(null);

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      {/* Page Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Recent Runs</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Execution history for every pipeline run.
            {(runs as any[]).length > 0 && (
              <span className="ml-1 text-muted-foreground">{(runs as any[]).length} runs total</span>
            )}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-card">
        <Table>
          <TableHeader className="sticky top-0 bg-background border-b border-border/40 z-10 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[180px]">Started</TableHead>
              <TableHead className="w-[80px]">Status</TableHead>
              <TableHead className="w-[60px]">Mode</TableHead>
              <TableHead className="text-right">Acquired</TableHead>
              <TableHead className="text-right">Classified</TableHead>
              <TableHead className="text-right text-emerald-500">Submitted</TableHead>
              <TableHead className="text-right text-red-400">Failed</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={7}>
                    <div className="h-4 bg-muted animate-pulse rounded" />
                  </TableCell>
                </TableRow>
              ))
            ) : (runs as any[]).length ? (
              (runs as any[]).map((run: any) => (
                <TableRow
                  key={run.run_id}
                  className="cursor-pointer hover:bg-muted/40 transition-colors border-b border-border/30"
                  onClick={() => setSelectedRun(run)}
                >
                  <TableCell className="font-mono text-xs">
                    <RelativeTime date={run.started_at} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={run.status ?? 'UNKNOWN'} />
                  </TableCell>
                  <TableCell>
                    <span className={`text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded ${
                      run.dry_run
                        ? 'bg-muted text-muted-foreground'
                        : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                    }`}>
                      {run.dry_run ? 'DRY' : 'LIVE'}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{run.acquired ?? 0}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{run.classified ?? 0}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums text-emerald-500 font-medium">{run.submitted ?? 0}</TableCell>
                  <TableCell className={`text-right font-mono tabular-nums ${run.failed > 0 ? 'text-red-400 font-semibold' : 'text-muted-foreground'}`}>
                    {run.failed ?? 0}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center text-muted-foreground text-xs">
                  No runs found. Launch the pipeline to get started.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Run Detail Sheet */}
      <Sheet open={!!selectedRun} onOpenChange={open => !open && setSelectedRun(null)}>
        <SheetContent className="w-[480px] sm:w-[520px] flex flex-col p-0 border-l border-border/50">
          <SheetHeader className="px-5 py-4 border-b border-border/40 bg-secondary/20">
            <div className="flex items-center justify-between">
              <SheetTitle className="text-sm font-semibold">Run Details</SheetTitle>
              {selectedRun && <CopyButton value={selectedRun.run_id} />}
            </div>
            <p className="text-[10px] font-mono text-muted-foreground mt-1 truncate">
              {selectedRun?.run_id}
            </p>
          </SheetHeader>
          <ScrollArea className="flex-1">
            {selectedRun && (
              <div className="px-5 py-5 space-y-6">
                {/* Overview */}
                <div className="space-y-0">
                  <MetaRow label="Status"    value={<StatusBadge status={selectedRun.status} />} />
                  <MetaRow label="Started"   value={<RelativeTime date={selectedRun.started_at} />} />
                  <MetaRow label="Mode"      value={selectedRun.dry_run ? 'Dry Run' : 'Live'} />
                  <MetaRow label="Acquired"  value={selectedRun.acquired ?? 0} />
                  <MetaRow label="Classified"value={selectedRun.classified ?? 0} />
                  <MetaRow label="Selected"  value={selectedRun.selected ?? 0} />
                  <MetaRow label="Submitted" value={<span className="text-emerald-500 font-semibold">{selectedRun.submitted ?? 0}</span>} />
                  <MetaRow label="Failed"    value={
                    selectedRun.failed > 0
                      ? <span className="text-red-400 font-semibold">{selectedRun.failed}</span>
                      : 0
                  } />
                </div>

                {/* Cache Performance */}
                {selectedRun.cache_metrics && Object.keys(selectedRun.cache_metrics).length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">Cache Performance</p>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { label: 'LLM',       hits: selectedRun.cache_metrics.llm_hits,       misses: selectedRun.cache_metrics.llm_misses       },
                        { label: 'Embedding', hits: selectedRun.cache_metrics.embedding_hits,  misses: selectedRun.cache_metrics.embedding_misses  },
                        { label: 'Detail',    hits: selectedRun.cache_metrics.detail_hits,     misses: selectedRun.cache_metrics.detail_misses     },
                        { label: 'HTTP',      hits: selectedRun.cache_metrics.http_hits,       misses: selectedRun.cache_metrics.http_misses       },
                      ].map(c => {
                        const total = (c.hits ?? 0) + (c.misses ?? 0);
                        const rate  = total > 0 ? Math.round(((c.hits ?? 0) / total) * 100) : 0;
                        return (
                          <div key={c.label} className="bg-muted/30 rounded p-3">
                            <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">{c.label}</p>
                            <p className="text-xs font-mono">{c.hits ?? 0} hits / {c.misses ?? 0} miss</p>
                            <p className={`text-[10px] font-mono mt-0.5 ${rate >= 80 ? 'text-emerald-500' : 'text-muted-foreground'}`}>{rate}% hit rate</p>
                          </div>
                        );
                      })}
                    </div>
                    <div className="mt-3 space-y-0">
                      <MetaRow
                        label="Lookup Time"
                        value={<span className="font-mono">{selectedRun.cache_metrics.total_lookup_time_ms?.toFixed(1) ?? '—'}ms</span>}
                      />
                      <MetaRow
                        label="Save Time"
                        value={<span className="font-mono">{selectedRun.cache_metrics.total_save_time_ms?.toFixed(1) ?? '—'}ms</span>}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </div>
  );
}
