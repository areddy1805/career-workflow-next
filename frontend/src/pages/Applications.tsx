import { useState, useMemo } from 'react';
import {
  useManualReviewQueue,
  useExternalApplyQueue,
  useOtherActionQueue,
} from '@/lib/hooks';
import { cn, formatSalary } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';
import { JobDrawer } from '@/components/JobDrawer';
import { ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { useSortable, sortData } from '@/hooks/useSortable';
import { SortableHeader } from '@/components/SortableHeader';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { EmptyState } from '@/components/operations/EmptyState';
import { ErrorState } from '@/components/operations/ErrorState';

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
    return <GridSkeleton rows={5} className="flex-1" />;
  }

  if (data.isError) {
    return (
      <div className="flex-1">
        <ErrorState message="Queue could not be loaded." onRetry={() => data.refetch()} />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        title="Queue clear"
        description="You're all caught up in this queue."
      />
    );
  }

  return (
    <div className="rounded-md border border-border bg-surface overflow-x-auto max-w-full w-full">
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
            const scoreClass = score >= 70 ? 'text-healthy' : score >= 40 ? 'text-degraded' : 'text-failed';

            return (
              <TableRow
                key={item.job_id}
                tabIndex={0}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick(item.job_id); } }}
                onClick={() => onRowClick(item.job_id)}
                className="hover:bg-muted/20 cursor-pointer transition-colors group border-b border-border/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
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
    <div className="h-full flex flex-col">
      <PageHeader
        coordinate="02 · 02"
        title="Inbox"
        subtitle={`Jobs that require your attention before the pipeline continues.${totalCount > 0 ? ` ${totalCount} item${totalCount !== 1 ? 's' : ''} pending.` : ''}`}
      />

      <Tabs value={activeTab} onValueChange={v => setActiveTab(v as TabId)}>
        <TabsList className="w-full justify-start px-1 overflow-x-auto">
          {TABS.map(tab => {
            const count = counts[tab.id];
            return (
              <TabsTrigger key={tab.id} value={tab.id} className="gap-2">
                {tab.label}
                {count != null && (
                  <span className={cn(
                    'font-mono text-[9px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center leading-none',
                    count > 0
                      ? 'bg-primary/15 text-primary'
                      : 'bg-muted/60 text-muted-foreground'
                  )}>
                    {count}
                  </span>
                )}
              </TabsTrigger>
            );
          })}
        </TabsList>
      </Tabs>

      <div className="flex-1 overflow-auto py-4">
        <div className="max-w-[1400px] min-w-0">
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
