import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchManualReviewQueue,
  fetchExternalApplyQueue,
  fetchOtherActionQueue,
} from '@/lib/api';
import { cn, formatSalary } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';
import { JobDrawer } from '@/components/JobDrawer';
import { ExternalLink, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

type TabId = 'manual-review' | 'external-apply' | 'other-action';

const TABS: Array<{ id: TabId; label: string; queryKey: string; fetchFn: any }> = [
  { id: 'manual-review',  label: 'Manual Review',  queryKey: 'manual-review',  fetchFn: fetchManualReviewQueue  },
  { id: 'external-apply', label: 'ATS Required',   queryKey: 'external-apply', fetchFn: fetchExternalApplyQueue },
  { id: 'other-action',   label: 'Needs Attention',queryKey: 'other-action',   fetchFn: fetchOtherActionQueue   },
];



export default function Queues() {
  const [activeTab, setActiveTab] = useState<TabId>('manual-review');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  // Pre-fetch all tab counts for display
  const mrData  = useQuery({ queryKey: ['queue', 'manual-review'],  queryFn: fetchManualReviewQueue,  staleTime: 30_000 });
  const eaData  = useQuery({ queryKey: ['queue', 'external-apply'], queryFn: fetchExternalApplyQueue, staleTime: 30_000 });
  const oaData  = useQuery({ queryKey: ['queue', 'other-action'],   queryFn: fetchOtherActionQueue,   staleTime: 30_000 });

  const mrItems = (mrData.data as any)?.items?.length ?? null;
  const eaItems = (eaData.data as any)?.items?.length ?? null;
  const oaItems = (oaData.data as any)?.items?.length ?? null;

  const counts: Record<TabId, number | null> = {
    'manual-review':  mrItems,
    'external-apply': eaItems,
    'other-action':   oaItems,
  };

  const totalCount = Object.values(counts).reduce<number>((acc, v) => acc + (v ?? 0), 0);

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      {/* Page Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Inbox</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Jobs that require your attention before the pipeline continues.
            {totalCount > 0 && (
              <span className="ml-1 text-primary font-medium">{totalCount} item{totalCount !== 1 ? 's' : ''} pending</span>
            )}
          </p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center border-b border-border/40 px-6 bg-background/80">
        {TABS.map(tab => {
          const count = counts[tab.id];
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-0 py-3 mr-6 text-xs font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border/50'
              )}
            >
              {tab.label}
              {count != null && (
                <span className={cn(
                  'text-[9px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center leading-none',
                  count > 0
                    ? 'bg-primary/15 text-primary'
                    : 'bg-muted/60 text-muted-foreground'
                )}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto bg-muted/5">
        <div className="max-w-[1400px] mx-auto p-6">
          {activeTab === 'manual-review'  && <QueueTable data={mrData} onRowClick={setSelectedJobId} />}
          {activeTab === 'external-apply' && <QueueTable data={eaData} onRowClick={setSelectedJobId} />}
          {activeTab === 'other-action'   && <QueueTable data={oaData} onRowClick={setSelectedJobId} />}
        </div>
      </div>

      <JobDrawer
        jobId={selectedJobId}
        open={!!selectedJobId}
        onOpenChange={open => !open && setSelectedJobId(null)}
        onTransitioned={() => setSelectedJobId(null)}
      />
    </div>
  );
}

// ─── Queue Table ──────────────────────────────────────────────────────────────

function QueueTable({
  data,
  onRowClick,
}: {
  data: any;
  onRowClick: (id: string) => void;
}) {
  if (data.isLoading) {
    return (
      <div className="bg-background border border-border/50 rounded-lg overflow-hidden">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-border/30 last:border-0 animate-pulse">
            <div className="flex-1 space-y-1.5">
              <div className="h-3.5 w-1/3 bg-muted rounded" />
              <div className="h-3 w-1/4 bg-muted rounded" />
            </div>
            <div className="h-5 w-16 bg-muted rounded" />
            <div className="h-5 w-24 bg-muted rounded" />
          </div>
        ))}
      </div>
    );
  }

  const items = data.data?.items ?? [];

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground border border-dashed border-border/50 rounded-lg bg-background">
        <CheckCircle className="w-8 h-8 mb-3 opacity-20" />
        <p className="text-sm font-medium">Inbox zero</p>
        <p className="text-xs mt-1 opacity-70">You're all caught up in this queue.</p>
      </div>
    );
  }

  return (
    <div className="bg-background border border-border/50 rounded-lg overflow-hidden">
      <table className="w-full text-left text-xs">
        <thead className="bg-muted/30 border-b border-border/40">
          <tr>
            <th className="px-4 py-3 font-medium text-muted-foreground w-1/3">Role</th>
            <th className="px-4 py-3 font-medium text-muted-foreground w-28">Details</th>
            <th className="px-4 py-3 font-medium text-muted-foreground w-20 text-center">Score</th>
            <th className="px-4 py-3 font-medium text-muted-foreground">AI Reason</th>
            <th className="px-4 py-3 font-medium text-muted-foreground w-28 text-right">Status</th>
            <th className="px-4 py-3 w-12" />
          </tr>
        </thead>
        <tbody className="divide-y divide-border/30">
          {items.map((item: any) => {
            const score = Number(item.ai_score ?? item.score ?? 0);
            const scoreClass = score >= 70 ? 'text-emerald-500' : score >= 40 ? 'text-amber-500' : 'text-red-400';

            return (
              <tr
                key={item.job_id}
                onClick={() => onRowClick(item.job_id)}
                className="hover:bg-muted/20 cursor-pointer transition-colors group"
              >
                <td className="px-4 py-3 align-top">
                  <div className="font-semibold text-sm text-foreground group-hover:text-primary transition-colors leading-tight">
                    {item.title}
                  </div>
                  <div className="text-muted-foreground mt-0.5">{item.company}</div>
                  {item.location && (
                    <div className="text-[10px] text-muted-foreground/60 mt-0.5">{item.location}</div>
                  )}
                </td>
                <td className="px-4 py-3 align-top space-y-1 text-muted-foreground">
                  {item.experience && <div>Exp: <span className="font-medium text-foreground">{item.experience}</span></div>}
                  {item.salary && <div>Pay: <span className="font-medium text-foreground">{formatSalary(item.salary)}</span></div>}
                </td>
                <td className="px-4 py-3 align-top text-center">
                  {score > 0 ? (
                    <span className={cn('font-mono font-bold tabular-nums', scoreClass)}>{score}</span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-4 py-3 align-top text-muted-foreground max-w-xs">
                  <p className="line-clamp-2 leading-relaxed">
                    {item.ai_reason ?? item.reason ?? item.notes?.[0] ?? 'Requires attention.'}
                  </p>
                </td>
                <td className="px-4 py-3 align-top text-right">
                  <StatusBadge status={item.workflow_status ?? item.status ?? 'UNKNOWN'} />
                </td>
                <td className="px-4 py-3 align-top" onClick={e => e.stopPropagation()}>
                  {item.apply_url && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-primary"
                      onClick={() => window.open(item.apply_url, '_blank', 'noopener,noreferrer')}
                      aria-label="Open job externally"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
