import { Link } from 'react-router-dom';
import { useDashboard, useRuntime, useManualReviewQueue, useExternalApplyQueue, useOtherActionQueue } from '@/lib/hooks';
import { PageHeader } from '@/components/operations/PageHeader';
import { Panel, PanelHeader } from '@/components/operations/Panel';
import { StateMarker, type StateSemantic } from '@/components/operations/StateMarker';
import { StationTopology, type TopoStation, type TopoBreaker } from '@/components/operations/StationTopology';
import { EnvelopeTrace } from '@/components/operations/EnvelopeTrace';
import { EmptyState } from '@/components/operations/EmptyState';
import { ErrorState } from '@/components/operations/ErrorState';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { RelativeTime } from '@/components/RelativeTime';

// ─── Overview — the Grid Control dispatch view (DESIGN.md §6) ────────────────
// Five zones, real data only: topology strip → operating-state bar →
// attention/fault conditions → execution activity → key readings.
// Not a metric-card grid; honest idle/unknown when data is absent.

const STAGES = [
  'preflight', 'acquisition', 'classification', 'selection',
  'application', 'reconciliation', 'strategy', 'report',
];

const STAGE_STATUS_STATE: Record<string, StateSemantic> = {
  SUCCESS: 'healthy',
  RUNNING: 'running',
  FAILED: 'failed',
  PARTIAL: 'degraded',
  PENDING: 'pending',
  CANCELLED: 'terminal',
  SKIPPED: 'blocked',
};

const STAGE_DETAIL_KEY: Record<string, string> = {
  acquisition: 'acquired',
  classification: 'classified',
  selection: 'selected',
};

const SCHEDULER_STATE: Record<string, { state: StateSemantic; pulse?: boolean }> = {
  RUNNING: { state: 'running', pulse: true },
  IDLE: { state: 'idle' },
  STOPPED: { state: 'blocked' },
  STALE: { state: 'degraded' },
  ORPHANED: { state: 'failed' },
};

function providerIsDegraded(status: unknown): boolean {
  const s = String(status ?? '').toLowerCase();
  return ['degraded', 'warning', 'error', 'down', 'failed'].some((w) => s.includes(w));
}

export default function Dashboard() {
  const dashboard = useDashboard();
  const runtime = useRuntime();
  const manual = useManualReviewQueue();
  const external = useExternalApplyQueue();
  const other = useOtherActionQueue();

  if (dashboard.isPending || runtime.isPending) {
    return (
      <div className="reveal">
        <PageHeader coordinate="01 · OVERVIEW" title="Overview" subtitle="System operating state, pipeline topology, and attention conditions." />
        <div className="flex flex-col gap-5">
          <GridSkeleton rows={2} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <GridSkeleton rows={4} />
            <GridSkeleton rows={4} />
          </div>
        </div>
      </div>
    );
  }

  if (dashboard.isError || runtime.isError) {
    return (
      <div className="reveal">
        <PageHeader coordinate="01 · OVERVIEW" title="Overview" subtitle="System operating state, pipeline topology, and attention conditions." />
        <ErrorState
          message={(dashboard.error as Error)?.message ?? (runtime.error as Error)?.message ?? 'Failed to load system state'}
          onRetry={() => { dashboard.refetch(); runtime.refetch(); }}
        />
      </div>
    );
  }

  const data = dashboard.data;
  const run = data?.latest_run ?? {};
  // latest_run merges run.json/result.json whose payload nests under `data`;
  // some environments surface it top-level. Read both, prefer top-level.
  const runData = run?.data ?? {};
  const runStages: Record<string, string> = run.stages ?? runData.stages ?? {};
  const runCounts: Record<string, number> = run.counts ?? runData.counts ?? {};
  const runStatus: string = String(run?.status ?? 'NONE').toUpperCase();
  const runId = run?.run_id ?? run?.id;
  const dryRun = run?.dry_run ?? runData?.dry_run;
  const startedAt = run?.started_at ?? runData?.started_at;
  void startedAt;
  const runLimit = typeof (run?.max_applications ?? runData?.max_applications) === 'number'
    ? (run?.max_applications ?? runData?.max_applications)
    : undefined;
  const lc = data?.lifecycle_metrics ?? {};
  const summary = data?.summary ?? {};
  const providers = data?.provider_health ?? {};

  // ── Zone 1: topology ──
  const stations: TopoStation[] = STAGES.map((id) => {
    const stageStatus = runStages[id];
    const state = stageStatus ? (STAGE_STATUS_STATE[stageStatus.toUpperCase()] ?? 'idle') : 'idle';
    const detailKey = STAGE_DETAIL_KEY[id];
    const count = detailKey && runCounts[detailKey] != null ? runCounts[detailKey] : undefined;
    return { id, label: id, state, detail: count != null ? String(count) : undefined };
  });
  const activeId = runStatus === 'RUNNING'
    ? (Object.entries(runStages).find(([, s]) => String(s).toUpperCase() === 'RUNNING')?.[0] ?? null)
    : null;
  const breakers: TopoBreaker[] = [];
  if (dryRun === true) {
    breakers.push({ after: 'selection', state: 'tagged', label: 'DRY RUN' });
  }

  // ── Zone 5: readings (real lifecycle accounting) ──
  const acquired = lc.acquired ?? 0;
  const submitted = lc.submitted ?? 0;
  const routed = lc.routed ?? 0;
  const selected = lc.selected ?? 0;
  const appFailed = lc.application_failed ?? 0;
  const submitRate = submitted + appFailed > 0 ? Math.round((submitted / (submitted + appFailed)) * 100) : null;
  const envelopePoints = [
    { x: 0, y: acquired },
    { x: 1, y: lc.classified ?? acquired },
    { x: 2, y: selected },
  ];

  // ── Zone 3: attention (real queues + degraded providers) ──
  const queueRows = [
    ...(manual.data?.items ?? []).map((i: any) => ({ ...i, lane: 'MANUAL' })),
    ...(external.data?.items ?? []).map((i: any) => ({ ...i, lane: 'EXTERNAL' })),
    ...(other.data?.items ?? []).map((i: any) => ({ ...i, lane: 'OTHER' })),
  ].slice(0, 8);
  const degradedProviders = Object.entries(providers)
    .filter(([, p]: [string, any]) => providerIsDegraded(p?.status))
    .map(([name, p]: [string, any]) => ({ name, status: String(p?.status ?? 'degraded') }));
  const attentionCount = queueRows.length + degradedProviders.length;

  // ── Zone 4: activity ──
  const lifecycleEntries = Object.entries(lc).filter(([, v]) => Number(v) > 0);
  const scheduler = runtime.data?.scheduler;
  const schedulerState = SCHEDULER_STATE[String(scheduler?.status ?? '').toUpperCase()] ?? { state: 'unknown' as StateSemantic };
  const hasRun = runStatus !== 'NONE' && runId != null;

  return (
    <div className="reveal flex flex-col gap-5">
      <PageHeader
        coordinate="01 · OVERVIEW"
        title="Overview"
        subtitle="Closed-loop AI job-operations control plane — topology, operating state, attention, and evidence."
      />

      {/* Zone 1 — topology strip */}
      <Panel>
        <PanelHeader
          index="01"
          title="Pipeline topology"
          actions={
            <Link to="/explorer" className="text-[12px] font-medium text-muted-foreground hover:text-foreground transition-colors">
              Explorer →
            </Link>
          }
        />
        <div className="px-4 py-4">
          <StationTopology
            stations={stations}
            breakers={breakers}
            activeId={activeId}
            running={runStatus === 'RUNNING'}
            ariaLabel="Pipeline topology — acquisition, classification, selection, application, reconciliation, strategy, report"
          />
          <div className="mt-3 pt-3 border-t border-border flex flex-wrap items-center gap-x-5 gap-y-1.5 text-meta text-muted-foreground">
            {hasRun ? (
              <>
                <span className="inline-flex items-center gap-2">
                  <StateMarker
                    state={STAGE_STATUS_STATE[runStatus] ?? (runStatus === 'NONE' ? 'idle' : 'unknown')}
                    label={runStatus}
                    pulse={runStatus === 'RUNNING'}
                  />
                  <span className="font-mono text-[11px] text-faint">RUN {runId}</span>
                </span>
                {run?.started_at && (
                  <span>
                    started <RelativeTime date={run.started_at} />
                  </span>
                )}
                {typeof run?.dry_run === 'boolean' && (
                  <span>{run.dry_run ? 'DRY RUN — execution isolated' : 'LIVE MODE — applications may submit'}</span>
                )}
              </>
            ) : (
              <span className="text-faint">No run on record — pipeline idle.</span>
            )}
          </div>
        </div>
      </Panel>

      {/* Zones 2 + 3 — operating state | attention */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel>
          <PanelHeader index="02" title="Operating state" />
          <div className="px-4 py-3 flex flex-col divide-y divide-border/70">
            <TruthRow
              label="Process"
              detail={String(scheduler?.status ?? 'UNKNOWN')}
              state={schedulerState.state}
              pulse={schedulerState.pulse}
            />
            <TruthRow
              label="Artifact"
              detail={hasRun ? `RUN ${runId} · ${runStatus}` : 'No run on record'}
              state={hasRun ? (STAGE_STATUS_STATE[runStatus] ?? 'unknown') : 'idle'}
            />
            <TruthRow
              label="Portfolio"
              detail={`${summary?.total_jobs ?? 0} jobs · ${summary?.total_applied ?? 0} applied · ${summary?.total_rejected ?? 0} rejected · ${summary?.total_offer ?? 0} offer`}
              state={(summary?.total_jobs ?? 0) > 0 ? 'healthy' : 'idle'}
            />
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            index="03"
            title="Attention & faults"
            actions={
              <Link to="/applications" className="text-[12px] font-medium text-muted-foreground hover:text-foreground transition-colors">
                Queues →
              </Link>
            }
          />
          {attentionCount > 0 ? (
            <div className="px-4 py-3 flex flex-col gap-2.5">
              {queueRows.length > 0 && (
                <div className="flex flex-col">
                  {queueRows.map((row: any) => (
                    <Link
                      key={row.job_id ?? row.id}
                      to="/applications"
                      className="flex items-center gap-3 px-1 py-1.5 rounded-sm text-[13px] hover:bg-muted/40 transition-colors group"
                    >
                      <StateMarker state="manual" label={row.lane} />
                      <span className="truncate text-foreground group-hover:underline underline-offset-2">{row.title ?? row.job_id}</span>
                      <span className="ml-auto text-meta text-faint truncate shrink-0">{row.company}</span>
                    </Link>
                  ))}
                </div>
              )}
              {degradedProviders.length > 0 && (
                <div className="flex flex-col gap-1">
                  {degradedProviders.map((p) => (
                    <Link key={p.name} to="/providers" className="flex items-center gap-3 px-1 py-1.5 rounded-sm text-[13px] hover:bg-muted/40 transition-colors group">
                      <StateMarker state="degraded" label="FAULT" />
                      <span className="text-foreground capitalize">{p.name}</span>
                      <span className="ml-auto text-meta text-faint">{p.status}</span>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <EmptyState title="No attention items" description="Queues clear, providers healthy." />
          )}
        </Panel>
      </div>

      {/* Zones 4 + 5 — execution activity | key readings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel>
          <PanelHeader index="04" title="Execution activity" />
          {hasRun ? (
            <div className="px-4 py-3 flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
                <span className="font-mono text-[11px] text-faint">RUN {runId}</span>
                <StateMarker
                  state={STAGE_STATUS_STATE[runStatus] ?? 'unknown'}
                  label={runStatus}
                  pulse={runStatus === 'RUNNING'}
                />
                {run?.started_at && <span className="text-meta text-muted-foreground">started <RelativeTime date={run.started_at} /></span>}
              </div>
              {Object.entries(runCounts).length > 0 && (
                <div className="flex flex-wrap gap-x-6 gap-y-1 pt-2 border-t border-border/70">
                  {Object.entries(runCounts).map(([k, v]) => (
                    <span key={k} className="flex items-baseline gap-1.5">
                      <span className="font-mono text-[13px] text-foreground tabular">{v}</span>
                      <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-faint">{k}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <EmptyState title="System idle — no recent run on record" />
          )}
          {lifecycleEntries.length > 0 && (
            <div className="px-4 pb-3">
              <div className="flex flex-wrap gap-x-6 gap-y-1 pt-3 border-t border-border/70">
                {lifecycleEntries.map(([k, v]) => (
                  <span key={k} className="flex items-baseline gap-1.5">
                    <span className="font-mono text-[13px] text-foreground tabular">{String(v)}</span>
                    <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-faint">{k.replace(/_/g, ' ')}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </Panel>

        <Panel>
          <PanelHeader index="05" title="Key readings" />
          <div className="px-4 py-3 flex flex-col gap-4">
            {acquired > 0 || selected > 0 ? (
              <EnvelopeTrace
                points={envelopePoints}
                bound={runLimit}
                boundLabel={runLimit != null ? `RUN LIMIT ${runLimit}` : undefined}
                xLabel="ACQ · CLS · SEL"
                yLabel="RECORDS"
              />
            ) : (
              <div className="text-meta text-faint">No throughput on record — run the pipeline to populate readings.</div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3 pt-1 border-t border-border/70">
              <Reading label="Acquired" value={acquired} />
              <Reading label="Submitted" value={submitted} />
              <Reading label="Submit rate" value={submitRate != null ? `${submitRate}%` : '—'} />
              <Reading label="Routed" value={routed} />
              <Reading label="Selected" value={selected} />
              <Reading label="App failed" value={appFailed} />
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function TruthRow({ label, detail, state, pulse }: { label: string; detail: string; state: StateSemantic; pulse?: boolean }) {
  return (
    <div className="flex items-center gap-3 py-2.5">
      <span className="w-20 shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-faint">{label}</span>
      <StateMarker state={state} label={detail} pulse={pulse} hideLabel />
      <span className="text-[13px] text-muted-foreground truncate">{detail}</span>
    </div>
  );
}

function Reading({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="min-w-0">
      <p className="font-mono text-[18px] leading-tight text-foreground tabular tracking-tight">{value}</p>
      <p className="font-mono text-[9px] uppercase tracking-[0.08em] text-faint mt-1">{label}</p>
    </div>
  );
}
