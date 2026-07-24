import { useState } from 'react';
import { useLedgerSearch, useLedgerStats } from '@/lib/hooks';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { StatusBadge } from '@/components/StatusBadge';
import { RelativeTime } from '@/components/RelativeTime';
import { Search, ChevronLeft, ChevronRight, FileJson } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useLedgerJob } from '@/lib/hooks';

export default function Ledger() {
  const [query, setQuery] = useState('');
  const [provider, setProvider] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading } = useLedgerSearch({ query, provider, status, limit, offset });
  const { data: stats } = useLedgerStats();

  const [selectedFingerprint, setSelectedFingerprint] = useState<string | null>(null);

  const { data: jobDetails, isLoading: detailsLoading } = useLedgerJob(selectedFingerprint || '');

  const items = data?.items || [];
  const total = data?.total || 0;
  const hasMore = offset + limit < total;

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Decision Ledger</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Operational state of every application tracked by the system.
          </p>
        </div>
        {stats && (
          <div className="flex gap-4">
            <div className="text-center">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Total</p>
              <p className="font-mono text-sm">{stats.total?.toLocaleString()}</p>
            </div>
            <div className="text-center">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Applied</p>
              <p className="font-mono text-sm text-emerald-500">{stats.applied?.toLocaleString()}</p>
            </div>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border/40 shrink-0 bg-secondary/10">
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input 
            placeholder="Search company or title..."
            value={query}
            onChange={e => { setQuery(e.target.value); setOffset(0); }}
            className="h-8 pl-9 text-xs"
          />
        </div>
        <select 
          className="h-8 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm"
          value={status}
          onChange={e => { setStatus(e.target.value); setOffset(0); }}
        >
          <option value="">All Statuses</option>
          <option value="applied">Applied</option>
          <option value="rejected">Rejected</option>
          <option value="qualified">Qualified</option>
        </select>
        <select 
          className="h-8 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm"
          value={provider}
          onChange={e => { setProvider(e.target.value); setOffset(0); }}
        >
          <option value="">All Providers</option>
          <option value="linkedin">LinkedIn</option>
          <option value="naukri">Naukri</option>
        </select>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto relative">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-background z-20 shadow-[0_1px_0_var(--border)]">
            <tr className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Company</th>
              <th className="px-4 py-2 font-medium">Title</th>
              <th className="px-4 py-2 font-medium">Location</th>
              <th className="px-4 py-2 font-medium">Provider</th>
              <th className="px-4 py-2 font-medium">Updated</th>
              <th className="px-4 py-2 font-medium w-16"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {items.map((job: any) => (
              <tr key={job.job_id} className="hover:bg-muted/50 transition-colors group">
                <td className="px-4 py-2">
                  <StatusBadge status={job.status} />
                </td>
                <td className="px-4 py-2 font-medium truncate max-w-[150px]">{job.company}</td>
                <td className="px-4 py-2 truncate max-w-[200px]">{job.title}</td>
                <td className="px-4 py-2 text-muted-foreground text-xs truncate max-w-[120px]">{job.location || '—'}</td>
                <td className="px-4 py-2">
                  <span className="font-mono text-[10px] text-muted-foreground">{job.source}</span>
                </td>
                <td className="px-4 py-2">
                  <RelativeTime date={job.last_updated_at} className="text-muted-foreground text-xs" />
                </td>
                <td className="px-4 py-2 text-right">
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-6 text-[10px] opacity-0 group-hover:opacity-100"
                    onClick={() => setSelectedFingerprint(job.job_id)}
                  >
                    View
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {isLoading && (
          <div className="absolute inset-0 bg-background/50 flex justify-center pt-20 z-30">
            <div className="flex items-center gap-2 text-sm text-muted-foreground font-mono bg-card px-4 py-2 border border-border/50 rounded-full shadow-sm h-10">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              Loading ledger...
            </div>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="h-12 border-t border-border/40 flex items-center justify-between px-4 bg-background shrink-0">
        <span className="text-xs text-muted-foreground">
          Showing {offset + 1}-{Math.min(offset + limit, total)} of {total.toLocaleString()}
        </span>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="h-7 text-xs" 
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
          >
            <ChevronLeft className="w-3 h-3 mr-1" /> Prev
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            className="h-7 text-xs"
            disabled={!hasMore}
            onClick={() => setOffset(offset + limit)}
          >
            Next <ChevronRight className="w-3 h-3 ml-1" />
          </Button>
        </div>
      </div>

      {/* Details Modal */}
      <Dialog open={!!selectedFingerprint} onOpenChange={(v) => !v && setSelectedFingerprint(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col p-0">
          <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0">
            <DialogTitle>Job Details: {selectedFingerprint}</DialogTitle>
          </DialogHeader>
          <div className="p-6 overflow-auto bg-muted/20 flex-1">
            {detailsLoading ? (
               <div className="animate-pulse space-y-4">
                 <div className="h-4 bg-muted w-1/3 rounded"></div>
                 <div className="h-32 bg-muted rounded"></div>
               </div>
            ) : jobDetails ? (
              <div className="space-y-6">
                <div>
                  <h3 className="font-semibold text-lg">{jobDetails.job.title}</h3>
                  <p className="text-muted-foreground">{jobDetails.job.company} • {jobDetails.job.location}</p>
                  <div className="mt-2 flex gap-2">
                    <StatusBadge status={jobDetails.job.status} />
                    <span className="text-xs bg-muted px-2 py-1 rounded">{jobDetails.job.source}</span>
                  </div>
                </div>
                
                <div>
                  <h4 className="text-sm font-semibold mb-3">Event Timeline</h4>
                  <div className="space-y-3 relative before:absolute before:left-[7px] before:top-2 before:bottom-2 before:w-px before:bg-border">
                    {jobDetails.events.map((evt: any) => (
                      <div key={evt.id} className="relative pl-6">
                        <div className="absolute left-[3px] top-1.5 w-2 h-2 rounded-full bg-border border-2 border-background" />
                        <div className="flex items-center gap-2 mb-1">
                          <StatusBadge status={evt.status} />
                          <RelativeTime date={evt.created_at} className="text-[10px] text-muted-foreground" />
                        </div>
                        {evt.detail && <p className="text-xs text-muted-foreground bg-background border rounded p-2">{evt.detail}</p>}
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                    <FileJson className="w-4 h-4" /> Raw Ledger Row
                  </h4>
                  <pre className="text-[10px] font-mono bg-background border p-4 rounded-md overflow-auto">
                    {JSON.stringify(jobDetails.job, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground text-center">Failed to load details</div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
