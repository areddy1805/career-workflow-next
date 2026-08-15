import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, ArrowRight, Bot, FileText, Loader2, SlidersHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { RelativeTime } from '@/components/RelativeTime';
import { useBrief, useCopilotOpportunity } from '@/lib/hooks';
import { verdictLabel } from '@/lib/types/copilot';
import { cn } from '@/lib/utils';

// Verdict banner colors keyed by verdict label (05_APPLICATION_BRIEF.md §4:
// Apply / Consider / Skip). The API's `verdict.class` is not trusted for
// styling — label → color keeps the banner deterministic.
const VERDICT_STYLES: Record<string, string> = {
  APPLY: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  CONSIDER: 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400',
  SKIP: 'border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400',
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
    return <ErrorState message="Missing opportunity id in route." />;
  }

  const title = oppQ.data?.title ?? 'Brief';
  const company = oppQ.data?.company ?? 'Application intelligence briefing';

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <header className="flex items-center justify-between gap-4 px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div className="min-w-0">
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <FileText className="w-4 h-4 text-primary shrink-0" /> {title}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{company}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
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
        </div>
      </header>

      <div className="flex-1 overflow-auto p-6">
        {briefQ.isLoading && <LoadingState />}
        {briefQ.isError && (
          <ErrorState
            message={briefQ.error?.message ?? 'Failed to load brief.'}
            onRetry={() => briefQ.refetch()}
          />
        )}
        {!briefQ.isLoading &&
          !briefQ.isError &&
          (!briefQ.data || briefQ.data.sections.length === 0) && (
            <EmptyState />
          )}
        {briefQ.data && briefQ.data.sections.length > 0 && (
          <div className="max-w-3xl mx-auto space-y-4 pb-8">
            {verdict && (
              <div
                className={cn(
                  'rounded-lg border px-4 py-3 flex items-center justify-between gap-4',
                  VERDICT_STYLES[verdict.toUpperCase()] ??
                    'border-border bg-card text-foreground',
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
                className="bg-card border border-border/60 rounded-xl p-4 space-y-2 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-sm font-semibold">{s.title}</h2>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {s.llm_augmented && (
                      <span
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-600 dark:text-purple-400 text-[10px] font-semibold font-mono uppercase tracking-wide"
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

// ─── States ──────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="max-w-3xl mx-auto space-y-4 animate-pulse" aria-label="Loading brief">
      <div className="h-16 bg-muted/50 rounded-lg" />
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-28 bg-muted/50 rounded-xl" />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="max-w-sm mx-auto bg-card border border-border/60 rounded-xl p-8 text-center space-y-3 shadow-sm mt-8">
      <FileText className="w-8 h-8 text-muted-foreground/40 mx-auto" aria-hidden="true" />
      <p className="text-sm font-medium">No brief yet</p>
      <p className="text-xs text-muted-foreground">
        This opportunity has no brief sections. Briefs are generated when an
        application flow starts.
      </p>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="max-w-sm mx-auto bg-card border border-border/60 rounded-xl p-8 text-center space-y-3 shadow-sm mt-8">
      <AlertCircle className="w-8 h-8 text-red-500/70 mx-auto" aria-hidden="true" />
      <p className="text-sm font-medium">Could not load brief</p>
      <p className="text-xs text-muted-foreground break-words">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <Loader2 className="w-3.5 h-3.5" /> Retry
        </Button>
      )}
    </div>
  );
}
