import { useMemo, useState } from 'react';
import { AlertCircle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { RelativeTime } from '@/components/RelativeTime';
import { StatusBadge } from '@/components/StatusBadge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useCopilotOpportunities, useSession, useSessions } from '@/lib/hooks';
import { cn } from '@/lib/utils';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { EmptyState as SharedEmptyState } from '@/components/operations/EmptyState';
import { ErrorState as SharedErrorState } from '@/components/operations/ErrorState';

const humanize = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export default function History() {
  const sessionsQ = useSessions(100);
  const oppsQ = useCopilotOpportunities();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Lazily resolve opportunity title/company from the session's opportunity_id
  // (sessions carry only the id; 07_UI §3.5).
  const oppMap = useMemo(() => {
    const map = new Map<string, { title: string; company: string; application_strategy: string }>();
    for (const o of oppsQ.data?.data ?? []) {
      map.set(o.opportunity_id, {
        title: o.title,
        company: o.company,
        application_strategy: o.application_strategy,
      });
    }
    return map;
  }, [oppsQ.data]);

  const sessions = sessionsQ.data?.data ?? [];

  const toggleSelect = (sessionId: string) =>
    setSelectedId((cur) => (cur === sessionId ? null : sessionId));

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <PageHeader
        coordinate="03 · 02"
        title="History"
        subtitle="Application sessions and their event timelines."
      />

      <div className="flex-1 overflow-auto">
        {sessionsQ.isLoading && <GridSkeleton rows={5} className="max-w-5xl mx-auto" />}
        {sessionsQ.isError && (
          <SharedErrorState
            message={sessionsQ.error?.message ?? 'Failed to load sessions.'}
            onRetry={() => sessionsQ.refetch()}
            className="max-w-5xl mx-auto mt-2"
          />
        )}
        {!sessionsQ.isLoading && !sessionsQ.isError && sessions.length === 0 && (
          <SharedEmptyState
            title="No sessions yet"
            description="Sessions appear here once you start an application flow."
            className="max-w-5xl mx-auto mt-8"
          />
        )}
        {!sessionsQ.isLoading && !sessionsQ.isError && sessions.length > 0 && (
          <div className="max-w-5xl mx-auto space-y-4 pb-8">
            <div className="bg-surface border border-border rounded-md overflow-hidden">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent border-b border-border/40">
                    <TableHead>Opportunity</TableHead>
                    <TableHead>Strategy</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Submitted</TableHead>
                    <TableHead>Outcome at</TableHead>
                    <TableHead className="text-right">Effort saved</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sessions.map((s) => {
                    const opp = oppMap.get(s.opportunity_id);
                    const selected = selectedId === s.session_id;
                    return (
                      <TableRow
                        key={s.session_id}
                        tabIndex={0}
                        role="button"
                        aria-expanded={selected}
                        aria-label={`Session for ${opp?.title ?? s.opportunity_id} — ${s.state}${s.outcome ? `, outcome ${s.outcome}` : ''}`}
                        onClick={() => toggleSelect(s.session_id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            toggleSelect(s.session_id);
                          }
                        }}
                        className={cn('cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring', selected && 'bg-muted/40')}
                      >
                        <TableCell>
                          <p className="text-[13px] font-medium">{opp?.title ?? s.opportunity_id}</p>
                          <p className="text-[11px] text-muted-foreground font-mono mt-0.5">
                            {opp?.company ?? 'Unknown company'}
                          </p>
                        </TableCell>
                        <TableCell className="text-xs">
                          {opp?.application_strategy ? humanize(opp.application_strategy) : '—'}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={s.state} />
                        </TableCell>
                        <TableCell>{s.outcome ? <StatusBadge status={s.outcome} /> : '—'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          <RelativeTime date={s.created_at} />
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {s.submitted_at ? <RelativeTime date={s.submitted_at} /> : '—'}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {s.outcome_at ? <RelativeTime date={s.outcome_at} /> : '—'}
                        </TableCell>
                        <TableCell className="text-right text-xs text-muted-foreground">
                          {/* Effort saved is not computed yet (07_UI §3.5) */}
                          —
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            {selectedId && (
              <SessionTimeline sessionId={selectedId} onClose={() => setSelectedId(null)} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Session detail (07_UI §3.5: row → event timeline, ADR-012 reconciliation) ──

function SessionTimeline({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const detailQ = useSession(sessionId);

  return (
    <section
      aria-label="Session timeline"
      className="bg-surface border border-border rounded-md"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <h2 className="text-sm font-semibold">Session timeline</h2>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close session timeline">
          <X className="w-3.5 h-3.5" />
        </Button>
      </div>

      <div className="p-4 space-y-4">
        {detailQ.isLoading && (
          <GridSkeleton rows={3} aria-label="Loading session detail" />
        )}
        {detailQ.isError && (
          <p className="text-xs text-failed flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5" aria-hidden="true" />
            {detailQ.error?.message ?? 'Failed to load session detail.'}
          </p>
        )}
        {!detailQ.isLoading && !detailQ.isError && detailQ.data && (
          <>
            {/* ADR-012: session state + recorded outcome shown side by side */}
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={detailQ.data.session.state} />
              {detailQ.data.session.outcome ? (
                <StatusBadge status={detailQ.data.session.outcome} />
              ) : (
                <span className="text-[10px] font-mono uppercase tracking-wide text-muted-foreground">
                  no outcome
                </span>
              )}
              <span className="text-[10px] font-mono text-muted-foreground ml-auto">
                {detailQ.data.session.profile_id} · {detailQ.data.session.session_id}
              </span>
            </div>

            {detailQ.data.events.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No events recorded for this session yet.
              </p>
            ) : (
              <ol className="space-y-2">
                {[...detailQ.data.events]
                  .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
                  .map((e) => (
                    <li
                      key={`${e.session_id}-${e.seq}`}
                      className="flex items-center gap-3 text-xs"
                    >
                      <span className="text-muted-foreground whitespace-nowrap font-mono w-32 shrink-0">
                        <RelativeTime date={e.occurred_at} />
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono text-[10px] uppercase tracking-wide">
                        {e.event_type}
                      </span>
                    </li>
                  ))}
              </ol>
            )}
          </>
        )}
      </div>
    </section>
  );
}
