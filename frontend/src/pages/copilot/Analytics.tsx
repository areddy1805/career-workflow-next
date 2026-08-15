import { useMemo, type ReactNode } from 'react';
import {
  AlertCircle,
  BarChart3,
  Database,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAnalytics } from '@/lib/hooks';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import type {
  AnalyticsData,
  FunnelConversions,
  FunnelStageCounts,
  LlmTrendPoint,
} from '@/lib/types/copilot';

// ─── Frozen display order (backend funnel.py `_STAGE_ORDER`, CP-8-01) ─────
// `viewed` = `briefed` (no brief-read event table) and `shortlisted` =
// `interview` (D-014 stage mapping) — documented D-row candidate mappings.
const FUNNEL_STAGES: { key: keyof FunnelStageCounts; label: string }[] = [
  { key: 'ingested', label: 'Ingested' },
  { key: 'briefed', label: 'Briefed' },
  { key: 'viewed', label: 'Viewed' },
  { key: 'applied', label: 'Applied' },
  { key: 'submitted', label: 'Submitted' },
  { key: 'shortlisted', label: 'Shortlisted' },
  { key: 'interview', label: 'Interview' },
  { key: 'offer', label: 'Offer' },
];

const FUNNEL_COLORS = [
  'bg-sky-500/80',
  'bg-cyan-500/80',
  'bg-teal-500/80',
  'bg-emerald-500/80',
  'bg-lime-500/80',
  'bg-amber-500/80',
  'bg-orange-500/80',
  'bg-rose-500/80',
];

const SOURCE_LABELS: Record<string, string> = {
  stored: 'Stored',
  deterministic: 'Deterministic',
  llm: 'LLM',
  manual: 'Manual',
};

// ─── Formatting helpers ────────────────────────────────────────────────────

/** Fraction (0–1) → percent string, e.g. 0.423 → "42.3%". */
const fmtRate = (v: number): string => `${(v * 100).toFixed(1)}%`;

/** Already-percent value (0–100) → percent string. */
const fmtPct = (v: number): string => `${v.toFixed(1)}%`;

/** Minutes → "42 min" / "6.5 min" (strip trailing .0). */
const fmtMin = (v: number): string => {
  const n = Math.round(v * 10) / 10;
  return `${Number.isInteger(n) ? n : n.toFixed(1)} min`;
};

/** "2025-01-05" → "01/05" (display only; avoids Date TZ shifts). */
const shortDate = (d: string): string => d.slice(5).replace('-', '/');

export default function Analytics() {
  const analytics = useAnalytics();
  const data = analytics.data;

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <PageHeader
        coordinate="03 · 03"
        title="Analytics"
        subtitle="Funnel, conversion, effort, answer-bank health, and learning calibration."
      />

      <div className="flex-1 overflow-auto pb-8">
        <div className="max-w-5xl mx-auto space-y-5 pb-8">
          {analytics.isLoading && (
            <div aria-label="Loading analytics">
              <GridSkeleton rows={4} />
            </div>
          )}

          {analytics.isError && (
            <div className="bg-surface border border-border/60 rounded-md p-8 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-failed/70 mx-auto" aria-hidden="true" />
              <p className="text-sm font-medium">Could not load analytics</p>
              <p className="text-xs text-muted-foreground break-words">
                {analytics.error?.message ?? 'Unknown error.'}
              </p>
              <Button variant="outline" size="sm" onClick={() => analytics.refetch()}>
                <Loader2 className="w-3.5 h-3.5" aria-hidden="true" /> Retry
              </Button>
            </div>
          )}

          {data && data.funnel.stages.ingested === 0 && (
            <div className="bg-surface border border-border/60 rounded-md p-8 text-center space-y-3">
              <Database className="w-8 h-8 text-muted-foreground/40 mx-auto" aria-hidden="true" />
              <p className="text-sm font-medium">No pipeline data yet</p>
              <p className="text-xs text-muted-foreground">
                Funnel, effort, and calibration populate as opportunities flow through the
                copilot. Everything below renders zeroed state.
              </p>
            </div>
          )}

          {data && (
            <>
              <SectionCard
                title="Funnel"
                description="Opportunity lifecycle counts and per-stage conversion rates (stage ÷ previous stage). Viewed = briefed and shortlisted = interview are the documented D-row proxy mappings (funnel.py)."
              >
                <FunnelBar
                  stages={data.funnel.stages}
                  conversions={data.funnel.conversions}
                />
              </SectionCard>

              <SectionCard
                title="Effort saved"
                description="Cumulative minutes saved, estimated manual application time minus assisted time (M11 deterministic model: 15 min manual baseline; assisted = median session submit time)."
              >
                <div className="grid sm:grid-cols-3 gap-3 mb-4">
                  <StatTile label="Manual estimate" value={fmtMin(data.effort.manual_estimate_min)} />
                  <StatTile label="Assisted estimate" value={fmtMin(data.effort.assisted_estimate_min)} />
                  <StatTile label="Saved" value={`${fmtMin(data.effort.saved_min)} (${fmtPct(data.effort.saved_pct)})`} />
                </div>
                <div className="space-y-3">
                  <CompareBar
                    label="Manual (baseline)"
                    value={data.effort.manual_estimate_min}
                    max={data.effort.manual_estimate_min}
                    color="bg-orange-500/60"
                  />
                  <CompareBar
                    label="Assisted (median)"
                    value={data.effort.assisted_estimate_min}
                    max={data.effort.manual_estimate_min}
                    color="bg-healthy/70"
                  />
                </div>
              </SectionCard>

              <SectionCard
                title="Answer bank health"
                description="Auto-resolve rate (stored + deterministic ÷ total), correction rate (manual or confirmed ÷ total), and the LLM call trend (M03/M04/M10 proxies)."
              >
                <div className="grid sm:grid-cols-3 gap-3 mb-4">
                  <StatTile label="Total answers" value={String(data.answer_health.total)} />
                  <StatTile label="Auto-resolve rate" value={fmtPct(data.answer_health.auto_resolve_rate)} />
                  <StatTile label="Correction rate" value={fmtPct(data.answer_health.correction_rate)} />
                </div>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                      Answers by source
                    </p>
                    <div className="space-y-2.5">
                      {Object.entries(data.answer_health.by_source).map(([source, count]) => (
                        <SourceRow
                          key={source}
                          label={SOURCE_LABELS[source] ?? source}
                          count={count}
                          total={data.answer_health.total}
                        />
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                      LLM-resolved answers per day (last 30 days)
                    </p>
                    <TrendChart points={data.llm_trend} />
                  </div>
                </div>
              </SectionCard>

              <SectionCard
                title="Learning calibration"
                description="Predicted (stored brief interview_probability) vs actual interview outcome per opportunity — mean absolute error over the paired sample (M09)."
              >
                <div className="grid sm:grid-cols-3 gap-3 mb-4">
                  <StatTile
                    label="Mean abs error"
                    value={data.calibration.mean_abs_error == null ? '—' : data.calibration.mean_abs_error.toFixed(3)}
                  />
                  <StatTile label="Paired sample" value={String(data.calibration.sample_count)} />
                  <StatTile
                    label="Actual interview rate"
                    value={
                      data.calibration.sample_count === 0
                        ? '—'
                        : fmtRate(
                            data.calibration.pairs.filter((p) => p.actual === 1).length /
                              data.calibration.sample_count,
                          )
                    }
                  />
                </div>
                {data.calibration.sample_count > 0 && (
                  <CalibrationBars data={data} />
                )}
                {data.calibration.sample_count === 0 && (
                  <p className="text-xs text-muted-foreground">
                    No opportunities have both a stored interview probability and a recorded
                    learning outcome yet — pairs form once both exist.
                  </p>
                )}
              </SectionCard>

              <SectionCard
                title="Conversion by provider / ATS / profile"
                description="Response and conversion rates broken down by provider, ATS type, and resume profile. The derivations exist but no endpoint exposes them yet — read-only pending display."
              >
                <div className="grid sm:grid-cols-3 gap-3">
                  <PendingCard
                    title="By provider"
                    body="provider_success() (src/copilot/learning/provider_success.py, CP-7-05) derives per-provider outcome counts, interview_rate / offer_rate, median_days_to_response, and best_strategy from copilot_learning_outcomes."
                  />
                  <PendingCard
                    title="By ATS type"
                    body="Same module derives by_ats_type buckets plus routing_preference (ATS ranked by offer_rate). Pure derivations — nothing consumes them yet."
                  />
                  <PendingCard
                    title="By resume profile"
                    body="Outcome rows carry resume_profile; per-profile applied / interview / offer conversion is derivable the same way but has no frozen endpoint."
                  />
                </div>
              </SectionCard>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Chart components ──────────────────────────────────────────────────────

function FunnelBar({
  stages,
  conversions,
}: {
  stages: FunnelStageCounts;
  conversions: FunnelConversions;
}) {
  const max = Math.max(...FUNNEL_STAGES.map((s) => stages[s.key]), 1);
  const convOf = (key: keyof FunnelStageCounts): number | null =>
    key === 'ingested' ? null : (conversions[key as keyof FunnelConversions] ?? null);

  return (
    <div>
      <div
        role="img"
        aria-label={`Application funnel — ${FUNNEL_STAGES.map(
          (s) => `${s.label}: ${stages[s.key]}`,
        ).join(', ')}`}
        className="flex h-8 w-full overflow-hidden rounded-lg border border-border/60"
      >
        {FUNNEL_STAGES.map((s, i) => {
          const count = stages[s.key];
          if (count <= 0) return null;
          return (
            <div
              key={s.key}
              title={`${s.label}: ${count}`}
              className={`${FUNNEL_COLORS[i % FUNNEL_COLORS.length]} h-full min-w-[2px]`}
              style={{ width: `${(count / max) * 100}%` }}
            />
          );
        })}
      </div>
      <ul className="mt-3 space-y-1.5">
        {FUNNEL_STAGES.map((s, i) => {
          const conv = i === 0 ? null : convOf(s.key);
          return (
            <li key={s.key} className="flex items-center gap-2.5 text-[13px]">
              <span
                className={`w-2 h-2 rounded-sm shrink-0 ${FUNNEL_COLORS[i % FUNNEL_COLORS.length]}`}
                aria-hidden="true"
              />
              <span className="flex-1 text-muted-foreground">{s.label}</span>
              <span className="font-mono">{stages[s.key]}</span>
              <span className="w-16 text-right font-mono text-xs text-muted-foreground">
                {conv == null ? '—' : fmtRate(conv)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function TrendChart({ points }: { points: LlmTrendPoint[] }) {
  const max = Math.max(...points.map((p) => p.count), 1);
  return (
    <div>
      <div className="flex items-end gap-[2px] h-28">
        {points.map((p) => (
          <div
            key={p.date}
            role="img"
            aria-label={`${shortDate(p.date)}: ${p.count} LLM-resolved answers`}
            title={`${p.date}: ${p.count}`}
            className="flex-1 min-w-0 rounded-t-sm bg-primary/60 hover:bg-primary transition-colors"
            style={{ height: `${(p.count / max) * 100}%` }}
          />
        ))}
      </div>
      <div className="flex gap-[2px] mt-1.5" aria-hidden="true">
        {points.map((p, i) => (
          <div
            key={p.date}
            className="flex-1 min-w-0 text-center text-[9px] font-mono text-muted-foreground/70 truncate"
          >
            {i % 5 === 0 ? shortDate(p.date) : ''}
          </div>
        ))}
      </div>
    </div>
  );
}

function CompareBar({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12px] mb-1">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono">{fmtMin(value)}</span>
      </div>
      <div
        role="img"
        aria-label={`${label}: ${fmtMin(value)} of ${fmtMin(max)}`}
        className="h-2.5 w-full rounded-full bg-muted/50 overflow-hidden"
      >
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.min((value / Math.max(max, 0.1)) * 100, 100)}%` }}
        />
      </div>
    </div>
  );
}

function CalibrationBars({ data }: { data: AnalyticsData }) {
  const { avgPredicted, actualRate } = useMemo(() => {
    const n = data.calibration.pairs.length;
    return {
      avgPredicted: data.calibration.pairs.reduce((s, p) => s + p.predicted, 0) / n,
      actualRate: data.calibration.pairs.reduce((s, p) => s + p.actual, 0) / n,
    };
  }, [data.calibration.pairs]);

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-baseline justify-between text-[12px] mb-1">
          <span className="text-muted-foreground">Avg predicted probability</span>
          <span className="font-mono">{fmtRate(avgPredicted)}</span>
        </div>
        <div
          role="img"
          aria-label={`Average predicted interview probability: ${fmtRate(avgPredicted)}`}
          className="h-2.5 w-full rounded-full bg-muted/50 overflow-hidden"
        >
          <div
            className="h-full rounded-full bg-sky-500/70"
            style={{ width: `${Math.min(avgPredicted * 100, 100)}%` }}
          />
        </div>
      </div>
      <div>
        <div className="flex items-baseline justify-between text-[12px] mb-1">
          <span className="text-muted-foreground">Actual interview rate</span>
          <span className="font-mono">{fmtRate(actualRate)}</span>
        </div>
        <div
          role="img"
          aria-label={`Actual interview rate: ${fmtRate(actualRate)}`}
          className="h-2.5 w-full rounded-full bg-muted/50 overflow-hidden"
        >
          <div
            className="h-full rounded-full bg-healthy/70"
            style={{ width: `${Math.min(actualRate * 100, 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function SourceRow({ label, count, total }: { label: string; count: number; total: number }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12px] mb-1">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono">{count}</span>
      </div>
      <div
        role="img"
        aria-label={`${label}: ${count} of ${total} answers`}
        className="h-2 w-full rounded-full bg-muted/50 overflow-hidden"
      >
        <div
          className="h-full rounded-full bg-primary/60"
          style={{ width: `${total > 0 ? (count / total) * 100 : 0}%` }}
        />
      </div>
    </div>
  );
}

// ─── Presentational helpers ─────────────────────────────────────────────────

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-surface border border-border/60 rounded-md">
      <div className="px-4 py-3 border-b border-border/50">
        <h2 className="text-sm font-semibold">{title}</h2>
        {description && (
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        )}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/60 p-3 bg-muted/20">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
        {label}
      </p>
      <p className="text-base font-mono mt-1">{value}</p>
    </div>
  );
}

function PendingCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border/70 p-3.5 space-y-1.5">
      <div className="flex items-center gap-2">
        <BarChart3 className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" />
        <p className="text-xs font-semibold">{title}</p>
        <span className="ml-auto px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[10px] font-mono uppercase tracking-wide">
          Pending endpoint
        </span>
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed">{body}</p>
    </div>
  );
}
