import { useMemo, useState } from 'react';
import { AlertCircle, History as HistoryIcon, Inbox, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { RelativeTime } from '@/components/RelativeTime';
import { StatusBadge } from '@/components/StatusBadge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useCopilotOpportunities, useSession, useSessions } from '@/lib/hooks';
import { cn } from '@/lib/utils';

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
      <header className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <HistoryIcon className="w-4 h-4 text-primary" /> History
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Application sessions and their event timelines.
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-6">
        {sessionsQ.isLoading && <LoadingState />}
        {sessionsQ.isError && (
          <ErrorState
            message={sessionsQ.error?.message ?? 'Failed to load sessions.'}
            onRetry={() => sessionsQ.refetch()}
          />
        )}
        {!sessionsQ.isLoading && !sessionsQ.isError && sessions.length === 0 && (
          <EmptyState />
        )}
        {!sessionsQ.isLoading && !sessionsQ.isError && sessions.length > 0 && (
          <div className="max-w-5xl mx-auto space-y-4 pb-8">
            <div className="bg-card border border-border/60 rounded-xl shadow-sm overflow-hidden">
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
      className="bg-card border border-border/60 rounded-xl shadow-sm"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <h2 className="text-sm font-semibold">Session timeline</h2>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close session timeline">
          <X className="w-3.5 h-3.5" />
        </Button>
      </div>

      <div className="p-4 space-y-4">
        {detailQ.isLoading && (
          <div className="space-y-2 animate-pulse" aria-label="Loading session detail">
            <div className="h-8 bg-muted/50 rounded-md" />
            <div className="h-24 bg-muted/50 rounded-md" />
          </div>
        )}
        {detailQ.isError && (
          <p className="text-xs text-red-500 flex items-center gap-2">
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

// ─── States ──────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="max-w-5xl mx-auto space-y-3 animate-pulse" aria-label="Loading sessions">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-14 bg-muted/50 rounded-xl" />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="max-w-sm mx-auto bg-card border border-border/60 rounded-xl p-8 text-center space-y-3 shadow-sm mt-8">
      <Inbox className="w-8 h-8 text-muted-foreground/40 mx-auto" aria-hidden="true" />
      <p className="text-sm font-medium">No sessions yet</p>
      <p className="text-xs text-muted-foreground">
        Sessions appear here once you start an application flow.
      </p>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="max-w-sm mx-auto bg-card border border-border/60 rounded-xl p-8 text-center space-y-3 shadow-sm mt-8">
      <AlertCircle className="w-8 h-8 text-red-500/70 mx-auto" aria-hidden="true" />
      <p className="text-sm font-medium">Could not load sessions</p>
      <p className="text-xs text-muted-foreground break-words">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        <Loader2 className="w-3.5 h-3.5" /> Retry
      </Button>
    </div>
  );
}
