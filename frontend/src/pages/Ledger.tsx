import { useEffect, useRef, useState } from 'react';
import { useLedgerSearch, useLedgerStats, useLedgerJob } from '@/lib/hooks';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { StatusBadge } from '@/components/operations/StatusBadge';
import { StatRow } from '@/components/operations/StatRow';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { EmptyState } from '@/components/operations/EmptyState';
import { ErrorState } from '@/components/operations/ErrorState';
import { RelativeTime } from '@/components/RelativeTime';
import { Search, ChevronLeft, ChevronRight, FileJson, Cpu, MapPin, Building, Globe } from 'lucide-react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { CopyButton } from '@/components/CopyButton';
import { cn } from '@/lib/utils';

export default function Ledger() {
  const [query, setQuery] = useState('');
  const [provider, setProvider] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading, isError, refetch } = useLedgerSearch({ query, provider, status, limit, offset });
  const { data: stats } = useLedgerStats();

  const [selectedFingerprint, setSelectedFingerprint] = useState<string | null>(null);
  const { data: jobDetails, isLoading: detailsLoading } = useLedgerJob(selectedFingerprint || '');

  // Focus restoration — the sheet opens without a Radix trigger, so capture
  // the invoking row and return focus to it on close (keyboard accessibility).
  const sheetTriggerRef = useRef<HTMLElement | null>(null);
  const selectRow = (fp: string) => {
    sheetTriggerRef.current = document.activeElement as HTMLElement | null;
    setSelectedFingerprint(fp);
  };
  const closeSheet = () => {
    setSelectedFingerprint(null);
  };
  const restoreFocus = (e: Event) => {
    e.preventDefault();
    sheetTriggerRef.current?.focus?.();
    sheetTriggerRef.current = null;
  };
  useEffect(() => {
    if (!selectedFingerprint) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeSheet(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [selectedFingerprint]);

  const items = data?.items || [];
  const total = data?.total || 0;
  const hasMore = offset + limit < total;

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        coordinate="04 · 01"
        title="Decision Ledger"
        subtitle="Operational state and AI analysis for every discovered opportunity."
        actions={
          stats ? (
            <div className="flex items-center gap-6 text-right">
              <div>
                <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-widest font-semibold mb-0.5">Total Tracked</p>
                <p className="font-mono text-[13px] font-semibold text-foreground tracking-tight tabular-nums">{stats.total?.toLocaleString()}</p>
              </div>
              <div>
                <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-widest font-semibold mb-0.5">Total Applied</p>
                <p className="font-mono text-[13px] font-semibold text-healthy tracking-tight tabular-nums">{stats.applied?.toLocaleString()}</p>
              </div>
            </div>
          ) : null
        }
      />

      <div className="flex-1 flex flex-col min-h-0 bg-surface border border-border rounded-md">
        {/* Filters */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-surface/80 shrink-0">
          <div className="relative w-64 group">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-foreground transition-colors" />
            <Input 
              placeholder="Search companies, titles…"
              aria-label="Search ledger"
              value={query}
              onChange={e => { setQuery(e.target.value); setOffset(0); }}
              className="h-8 pl-9 text-xs bg-background/50 focus-visible:bg-background"
            />
          </div>
          <Select value={status} onValueChange={v => { setStatus(v); setOffset(0); }}>
            <SelectTrigger aria-label="Filter by status" className="h-8 w-auto min-w-[120px] text-xs">
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Statuses</SelectItem>
              <SelectItem value="applied">Applied</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
              <SelectItem value="qualified">Qualified</SelectItem>
            </SelectContent>
          </Select>
          <Select value={provider} onValueChange={v => { setProvider(v); setOffset(0); }}>
            <SelectTrigger aria-label="Filter by provider" className="h-8 w-auto min-w-[120px] text-xs">
              <SelectValue placeholder="All Providers" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Providers</SelectItem>
              <SelectItem value="linkedin">LinkedIn</SelectItem>
              <SelectItem value="naukri">Naukri</SelectItem>
              <SelectItem value="indeed">Indeed</SelectItem>
              <SelectItem value="google">Google</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto relative">
          <table className="w-full min-w-[900px] text-left border-collapse">
            <thead className="sticky top-0 bg-muted/30 z-20">
              <tr className="font-mono text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                <th className="px-4 py-3 border-b border-border w-32">Status</th>
                <th className="px-4 py-3 border-b border-border">Company</th>
                <th className="px-4 py-3 border-b border-border">Title</th>
                <th className="px-4 py-3 border-b border-border">Location</th>
                <th className="px-4 py-3 border-b border-border">Provider</th>
                <th className="px-4 py-3 border-b border-border">Updated</th>
                <th className="px-4 py-3 border-b border-border w-16"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {items.map((job: any) => (
                <tr 
                  key={job.job_id} 
                  tabIndex={0}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectRow(job.job_id); } }}
                  className="hover:bg-muted/30 transition-colors group cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                  onClick={() => selectRow(job.job_id)}
                >
                  <td className="px-4 py-3">
                    <StatusBadge 
                      status={['applied', 'submitted', 'offer', 'interview'].includes(job.status?.toLowerCase()) ? 'success' : job.status?.toLowerCase() === 'rejected' ? 'neutral' : 'info'} 
                      label={job.status} 
                    />
                  </td>
                  <td className="px-4 py-3 font-medium text-foreground text-[13px] truncate max-w-[200px]">{job.company}</td>
                  <td className="px-4 py-3 text-muted-foreground group-hover:text-foreground transition-colors text-[13px] truncate max-w-[250px]">{job.title}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs truncate max-w-[150px]">{job.location || '—'}</td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{job.source}</span>
                  </td>
                  <td className="px-4 py-3">
                    <RelativeTime date={job.last_updated_at} className="font-mono text-[11px] text-muted-foreground" />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ChevronRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity ml-auto" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {isError && (
            <div className="m-4">
              <ErrorState message="Ledger records could not be loaded." onRetry={() => refetch()} />
            </div>
          )}

          {!isError && isLoading && items.length === 0 && (
            <div className="m-4">
              <GridSkeleton rows={8} />
            </div>
          )}
          
          {!isError && !isLoading && items.length === 0 && (
            <EmptyState
              title="No records found"
              description="Try adjusting your filters or search query."
            />
          )}
        </div>

        {/* Pagination */}
        <div className="h-12 border-t border-border flex items-center justify-between px-4 bg-surface/80 shrink-0">
          <span className="text-[11px] font-mono text-muted-foreground">
            Showing {Math.min(offset + 1, total)}-{Math.min(offset + limit, total)} of {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-2">
            <Button 
              variant="outline" 
              size="sm" 
              className="h-7 text-[11px] font-medium px-2.5 bg-background hover:bg-muted" 
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              <ChevronLeft className="w-3 h-3 mr-1" /> Prev
            </Button>
            <Button 
              variant="outline" 
              size="sm" 
              className="h-7 text-[11px] font-medium px-2.5 bg-background hover:bg-muted"
              disabled={!hasMore}
              onClick={() => setOffset(offset + limit)}
            >
              Next <ChevronRight className="w-3 h-3 ml-1" />
            </Button>
          </div>
        </div>
      </div>

      {/* Details Sheet */}
      <Sheet open={!!selectedFingerprint} onOpenChange={(v) => !v && closeSheet()}>
        <SheetContent
          onCloseAutoFocus={restoreFocus}
          className="w-[480px] sm:w-[600px] flex flex-col p-0 border-l border-border bg-surface"
        >
          <SheetHeader className="px-6 py-5 border-b border-border bg-surface/80 shrink-0">
            <div className="flex items-center justify-between">
              <SheetTitle className="text-base font-semibold tracking-tight text-foreground">Intelligence Trace</SheetTitle>
              {selectedFingerprint && <CopyButton value={selectedFingerprint} className="h-8 w-8 text-muted-foreground hover:text-foreground" />}
            </div>
            <p className="text-[11px] font-mono text-muted-foreground mt-1 truncate tracking-tight">
              {selectedFingerprint}
            </p>
          </SheetHeader>
          <ScrollArea className="flex-1 bg-muted/10">
            <div className="p-6">
              {detailsLoading ? (
                 <GridSkeleton rows={4} />
              ) : jobDetails ? (
                <div className="space-y-8">
                  {/* Job Header */}
                  <div>
                    <h3 className="text-xl font-bold tracking-tight text-foreground mb-2">{jobDetails.job.title}</h3>
                    <div className="flex flex-col gap-1.5 mb-4">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Building className="w-4 h-4" />
                        <span className="font-medium text-foreground">{jobDetails.job.company}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <MapPin className="w-4 h-4" />
                        <span>{jobDetails.job.location}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Globe className="w-4 h-4" />
                        <span className="capitalize">{jobDetails.job.source}</span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <StatusBadge 
                        status={['applied', 'submitted', 'offer', 'interview'].includes(jobDetails.job.status?.toLowerCase()) ? 'success' : jobDetails.job.status?.toLowerCase() === 'rejected' ? 'neutral' : 'info'} 
                        label={jobDetails.job.status} 
                      />
                    </div>
                  </div>
                  
                  {/* AI Reasoning (If available) */}
                  {jobDetails.job.llm_analysis && (
                    <div>
                      <h4 className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3 flex items-center gap-2">
                        <Cpu className="w-3.5 h-3.5" />
                        AI Analysis
                      </h4>
                      <div className="bg-surface border border-border rounded-md p-4 space-y-3">
                        {typeof jobDetails.job.llm_analysis === 'object' ? (
                           <>
                              <StatRow label="Qualification" value={
                                <StatusBadge 
                                  status={jobDetails.job.llm_analysis.qualified ? 'success' : 'error'} 
                                  label={jobDetails.job.llm_analysis.qualified ? 'Qualified' : 'Unqualified'} 
                                />
                              } />
                              <div className="pt-2 border-t border-border">
                                <p className="text-[11px] font-semibold text-foreground mb-1">Reasoning</p>
                                <p className="text-xs text-muted-foreground leading-relaxed">
                                  {jobDetails.job.llm_analysis.reasoning || 'No detailed reasoning provided.'}
                                </p>
                              </div>
                           </>
                        ) : (
                          <p className="text-xs text-muted-foreground leading-relaxed">
                            {JSON.stringify(jobDetails.job.llm_analysis)}
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Event Timeline */}
                  <div>
                    <h4 className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-4">Event Timeline</h4>
                    <div className="space-y-4 relative before:absolute before:left-[7px] before:top-2 before:bottom-2 before:w-px before:bg-border/60">
                      {jobDetails.events.map((evt: any, i: number) => (
                        <div key={evt.id} className="relative pl-6">
                          <div className={cn(
                            "absolute left-[3px] top-1.5 w-2 h-2 rounded-full border-2 border-background",
                            i === 0 ? "bg-primary" : "bg-muted-foreground"
                          )} />
                          <div className="flex items-center gap-3 mb-1.5">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-foreground">{evt.status}</span>
                            <span className="text-muted-foreground/30">•</span>
                            <RelativeTime date={evt.created_at} className="text-[11px] font-mono text-muted-foreground" />
                          </div>
                          {evt.detail && (
                            <div className="text-xs text-muted-foreground bg-surface border border-border/50 rounded-md p-3 leading-relaxed">
                              {evt.detail}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Raw Data Dump */}
                  <div>
                    <h4 className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3 flex items-center gap-2">
                      <FileJson className="w-3.5 h-3.5" /> 
                      Raw Ledger Entity
                    </h4>
                    <div className="bg-console border border-border rounded-md overflow-hidden">
                      <pre className="text-[10px] font-mono text-console-foreground/75 p-4 overflow-auto max-h-[300px]">
                        {JSON.stringify(jobDetails.job, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground text-center py-12 text-sm">Failed to load details</div>
              )}
            </div>
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </div>
  );
}
