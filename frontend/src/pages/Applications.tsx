import { useState, useMemo } from 'react';
import {
  useManualReviewQueue,
  useExternalApplyQueue,
  useOtherActionQueue,
} from '@/lib/hooks';
import { cn, formatSalary } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';
import { JobDrawer } from '@/components/JobDrawer';
import { ExternalLink, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { useSortable, sortData } from '@/hooks/useSortable';
import { SortableHeader } from '@/components/SortableHeader';

type TabId = 'manual-review' | 'external-apply' | 'other-action';

const TABS: Array<{ id: TabId; label: string }> = [
  { id: 'manual-review',  label: 'Manual Review' },
  { id: 'external-apply', label: 'ATS Required' },
  { id: 'other-action',   label: 'Needs Attention' },
];

const QUEUE_SORT_TYPES = {
  title: 'text' as const,
  company: 'text' as const,
  score: 'number' as const,
  reason: 'text' as const,
  status: 'status' as const,
  location: 'text' as const,
};

function QueueTable({
  data,
  onRowClick,
}: {
  data: any;
  onRowClick: (id: string) => void;
}) {
  const { sort, handleSort } = useSortable(QUEUE_SORT_TYPES);
  const items = data.data?.items ?? [];
  const sortedItems = useMemo(
    () => sortData(items, sort, QUEUE_SORT_TYPES),
    [items, sort],
  );

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
      <Table>
        <TableHeader className="bg-muted/30">
          <TableRow className="hover:bg-transparent border-b border-border/40">
            <SortableHeader column="title" label="Role" sort={sort} onSort={handleSort} className="w-1/3" />
            <SortableHeader column="company" label="Company" sort={sort} onSort={handleSort} className="w-28" />
            <SortableHeader column="score" label="Score" sort={sort} onSort={handleSort} className="w-20 text-center" />
            <SortableHeader column="reason" label="AI Reason" sort={sort} onSort={handleSort} />
            <SortableHeader column="status" label="Status" sort={sort} onSort={handleSort} className="w-28 text-right" />
            <TableHead className="w-12" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedItems.map((item: any) => {
            const score = Number(item.ai_score ?? item.score ?? 0);
            const scoreClass = score >= 70 ? 'text-emerald-500' : score >= 40 ? 'text-amber-500' : 'text-red-400';

            return (
              <TableRow
                key={item.job_id}
                onClick={() => onRowClick(item.job_id)}
                className="hover:bg-muted/20 cursor-pointer transition-colors group border-b border-border/30"
              >
                <TableCell className="align-top">
                  <div className="font-semibold text-sm text-foreground group-hover:text-primary transition-colors leading-tight">
                    {item.title}
                  </div>
                  <div className="text-muted-foreground mt-0.5 text-xs">{item.company}</div>
                  {item.location && (
                    <div className="text-[10px] text-muted-foreground/60 mt-0.5">{item.location}</div>
                  )}
                </TableCell>
                <TableCell className="align-top text-xs text-muted-foreground">
                  {item.experience && <div>Exp: <span className="font-medium text-foreground">{item.experience}</span></div>}
                  {item.salary && <div>Pay: <span className="font-medium text-foreground">{formatSalary(item.salary)}</span></div>}
                </TableCell>
                <TableCell className="align-top text-center">
                  {score > 0 ? (
                    <span className={cn('font-mono font-bold tabular-nums', scoreClass)}>{score}</span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="align-top text-muted-foreground max-w-xs text-xs">
                  <p className="line-clamp-2 leading-relaxed">
                    {item.ai_reason ?? item.reason ?? item.notes?.[0] ?? 'Requires attention.'}
                  </p>
                </TableCell>
                <TableCell className="align-top text-right">
                  <StatusBadge status={item.workflow_status ?? item.status ?? 'UNKNOWN'} />
                </TableCell>
                <TableCell className="align-top" onClick={e => e.stopPropagation()}>
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
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

export default function Applications() {
  const [activeTab, setActiveTab] = useState<TabId>('manual-review');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const mrData  = useManualReviewQueue();
  const eaData  = useExternalApplyQueue();
  const oaData  = useOtherActionQueue();

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
