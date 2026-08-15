import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowRight, Bot, SlidersHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { RelativeTime } from '@/components/RelativeTime';
import { useBrief, useCopilotOpportunity } from '@/lib/hooks';
import { verdictLabel } from '@/lib/types/copilot';
import { cn } from '@/lib/utils';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { EmptyState as SharedEmptyState } from '@/components/operations/EmptyState';
import { ErrorState as SharedErrorState } from '@/components/operations/ErrorState';

// Verdict banner colors keyed by verdict label (05_APPLICATION_BRIEF.md §4:
// Apply / Consider / Skip). The API's `verdict.class` is not trusted for
// styling — label → color keeps the banner deterministic.
const VERDICT_STYLES: Record<string, string> = {
  APPLY: 'border-healthy/40 bg-healthy/10 text-healthy',
  CONSIDER: 'border-degraded/40 bg-degraded/10 text-degraded',
  SKIP: 'border-failed/40 bg-failed/10 text-failed',
};

export default function Brief() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  // "Show only certain facts" — client state only (05_APPLICATION_BRIEF.md §5).
  const [onlyCertain, setOnlyCertain] = useState(false);

  const briefQ = useBrief(id ?? '');
  const oppQ = useCopilotOpportunity(id ?? '');

  const sections = useMemo(() => {
    const all = briefQ.data?.sections ?? [];
    return onlyCertain ? all.filter((s) => !s.llm_augmented) : all;
  }, [briefQ.data, onlyCertain]);

  const verdict = verdictLabel(briefQ.data?.verdict);
  const verdictReason = briefQ.data?.verdict_reason ?? null;

  const hiddenCount = useMemo(() => {
    const all = briefQ.data?.sections ?? [];
    return onlyCertain ? all.filter((s) => s.llm_augmented).length : 0;
  }, [briefQ.data, onlyCertain]);

  if (!id) {
    return <SharedErrorState message="Missing opportunity id in route." />;
  }

  const title = oppQ.data?.title ?? 'Brief';
  const company = oppQ.data?.company ?? 'Application intelligence briefing';

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <PageHeader
        coordinate="03 · BRIEF"
        title={title}
        subtitle={company}
        actions={
          <>
            {briefQ.data && briefQ.data.sections.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                aria-pressed={onlyCertain}
                onClick={() => setOnlyCertain((v) => !v)}
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                {onlyCertain ? 'Showing certain facts only' : 'Show only certain facts'}
              </Button>
            )}
            <Button size="sm" onClick={() => navigate(`/copilot/apply/${id}`)}>
              Apply <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </>
        }
      />

      <div className="flex-1 overflow-auto pb-8">
        {briefQ.isLoading && <GridSkeleton rows={4} className="max-w-3xl mx-auto" />}
        {briefQ.isError && (
          <SharedErrorState
            message={briefQ.error?.message ?? 'Failed to load brief.'}
            onRetry={() => briefQ.refetch()}
            className="max-w-3xl mx-auto mt-2"
          />
        )}
        {!briefQ.isLoading &&
          !briefQ.isError &&
          (!briefQ.data || briefQ.data.sections.length === 0) && (
            <SharedEmptyState
              title="No brief yet"
              description="This opportunity has no brief sections. Briefs are generated when an application flow starts."
              className="max-w-3xl mx-auto mt-8"
            />
          )}
        {briefQ.data && briefQ.data.sections.length > 0 && (
          <div className="max-w-3xl mx-auto space-y-4 pb-8">
            {verdict && (
              <div
                className={cn(
                  'rounded-md border px-4 py-3 flex items-center justify-between gap-4',
                  VERDICT_STYLES[verdict.toUpperCase()] ??
                    'border-border bg-surface text-foreground',
                )}
              >
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider opacity-70">
                    Verdict
                  </p>
                  <p className="text-base font-semibold">{verdict}</p>
                  {verdictReason && (
                    <p className="text-xs text-muted-foreground mt-1">{verdictReason}</p>
                  )}
                </div>
                <div className="text-right text-[11px] text-muted-foreground space-y-0.5">
                  <p>
                    Generated <RelativeTime date={briefQ.data.generated_at} />
                  </p>
                  {briefQ.data.model_used && (
                    <p className="font-mono">Model: {briefQ.data.model_used}</p>
                  )}
                </div>
              </div>
            )}

            {onlyCertain && hiddenCount > 0 && (
              <p className="text-xs text-muted-foreground" role="status">
                {hiddenCount} LLM-augmented section{hiddenCount === 1 ? '' : 's'} hidden.
                Toggle the filter to show everything.
              </p>
            )}

            {sections.map((s) => (
              <article
                key={s.key}
                className="bg-surface border border-border rounded-md p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-sm font-semibold">{s.title}</h2>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {s.llm_augmented && (
                      <span
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-pending/10 text-pending text-[10px] font-semibold font-mono uppercase tracking-wide"
                        title="This section was augmented by an LLM"
                      >
                        <Bot className="w-3 h-3" /> LLM
                      </span>
                    )}
                    <span className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[10px] font-mono uppercase tracking-wide">
                      {s.provenance}
                    </span>
                  </div>
                </div>
                <p className="text-[13px] text-muted-foreground whitespace-pre-wrap leading-relaxed">
                  {s.content}
                </p>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
