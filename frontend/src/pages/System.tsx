import { useQuery } from '@tanstack/react-query';
import { fetchSystem } from '@/lib/api';
import { Activity, Server, Clock, Lock, Cpu, CheckCircle, AlertCircle } from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';
import { RelativeTime } from '@/components/RelativeTime';
import { cn } from '@/lib/utils';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { ErrorState } from '@/components/operations/ErrorState';

// ─── Reusable data row ────────────────────────────────────────────────────────

function DataRow({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border/20 last:border-0 text-xs gap-4">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className={cn('text-right', mono && 'font-mono')}>{value}</span>
    </div>
  );
}

// ─── Health module card ───────────────────────────────────────────────────────

function ModuleCard({
  icon: Icon,
  title,
  status,
  children,
}: {
  icon: React.ElementType;
  title: string;
  status?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border/50 rounded-md bg-surface overflow-hidden">
      <div className="h-10 px-4 border-b border-border/50 bg-muted/10 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          <Icon className="w-3.5 h-3.5" />
          {title}
        </div>
        {status && <StatusBadge status={status} />}
      </div>
      <div className="p-4 space-y-0">{children}</div>
    </div>
  );
}

// ─── Process alive indicator ──────────────────────────────────────────────────

function AliveIndicator({ alive }: { alive: boolean | undefined }) {
  if (alive == null) return <span className="text-muted-foreground">—</span>;
  return (
    <span className={cn('flex items-center gap-1.5 justify-end', alive ? 'text-healthy' : 'text-failed')}>
      {alive
        ? <CheckCircle className="w-3.5 h-3.5" />
        : <AlertCircle className="w-3.5 h-3.5" />}
      {alive ? 'Online' : 'Offline'}
    </span>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Runtime() {
  const { data: runtime, isLoading, isError, refetch } = useQuery({
    queryKey: ['runtime'],
    queryFn: fetchSystem,
    refetchInterval: 3000,
  });

  if (isError) {
    return (
      <div className="h-full p-6 max-w-4xl">
        <ErrorState message="System health telemetry could not be loaded." onRetry={() => refetch()} />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="h-full p-6 max-w-4xl">
        <GridSkeleton rows={5} />
      </div>
    );
  }

  const data: any = runtime || {};
  const {
    scheduler = {},
    pipeline = {},
    ui = {},
    latest_run_details = {}
  } = data;

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <PageHeader
        coordinate="06 · 01"
        title="System Health"
        subtitle="Real-time status of the scheduler, pipeline worker, and API server."
      />

      <div className="flex-1 overflow-auto max-w-4xl space-y-6 pb-8">

        {/* Process modules — 3 cards in a grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

          {/* Scheduler */}
          <ModuleCard icon={Clock} title="Scheduler" status={scheduler?.status ?? 'UNKNOWN'}>
            <DataRow label="Process"      value={<AliveIndicator alive={scheduler?.is_alive} />} />
            <DataRow label="Heartbeat"    value={scheduler?.heartbeat_age != null ? `${Math.round(scheduler.heartbeat_age)}s ago` : '—'} mono />
            <DataRow label="PID"          value={scheduler?.pid ?? '—'} mono />
          </ModuleCard>

          {/* Pipeline Worker */}
          <ModuleCard icon={Cpu} title="Pipeline Worker" status={pipeline?.status ?? 'IDLE'}>
            <DataRow label="Process"  value={<AliveIndicator alive={pipeline?.is_alive} />} />
            <DataRow label="Lock"     value={
              scheduler?.lock
                ? <span className="flex items-center gap-1.5 text-failed justify-end"><Lock className="w-3 h-3" /> Locked</span>
                : <span className="text-muted-foreground">Free</span>
            } />
            <DataRow label="PID"      value={pipeline?.pid ?? '—'} mono />
          </ModuleCard>

          {/* API Server */}
          <ModuleCard icon={Server} title="API Server" status={ui?.status ?? 'ONLINE'}>
            <DataRow label="Process" value={<AliveIndicator alive={true} />} />
            <DataRow label="PID"     value={ui?.pid ?? '—'} mono />
          </ModuleCard>

        </div>

        {/* Latest Run Detail */}
        {latest_run_details?.run_id && (
          <div className="space-y-4 pt-4 border-t border-border/50">
            <div>
              <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Last Run Telemetry</h2>
              <p className="text-[10px] text-muted-foreground/60 mt-0.5 font-mono">{latest_run_details.run_id}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

              {/* Run Overview */}
              <ModuleCard icon={Activity} title="Run Overview" status={latest_run_details.status}>
                <DataRow label="Started"   value={latest_run_details.started_at ? <RelativeTime date={latest_run_details.started_at} /> : '—'} />
                <DataRow label="Completed" value={latest_run_details.completed_at ? <RelativeTime date={latest_run_details.completed_at} /> : 'Running…'} />
                <DataRow label="Mode"      value={latest_run_details.dry_run ? 'Dry Run' : 'Live'} />
              </ModuleCard>

              {/* Stage Checklist */}
              <div className="border border-border/50 rounded-md bg-surface overflow-hidden">
                <div className="h-10 px-4 border-b border-border/50 bg-muted/10 flex items-center text-xs font-semibold text-muted-foreground uppercase tracking-wider gap-2">
                  <Cpu className="w-3.5 h-3.5" /> Stage Checklist
                </div>
                <div className="p-4 space-y-0">
                  {Object.entries(latest_run_details.stages ?? {}).map(([stage, status]: any) => (
                    <DataRow
                      key={stage}
                      label={stage.charAt(0).toUpperCase() + stage.slice(1)}
                      value={<StatusBadge status={String(status).toUpperCase()} />}
                    />
                  ))}
                </div>
              </div>

              {/* Acquisition Metrics */}
              <ModuleCard icon={Activity} title="Acquisition">
                <DataRow label="Jobs Acquired"      value={latest_run_details.acquisition?.acquired ?? latest_run_details.acquisition?.jobs ?? '—'} mono />
                <DataRow label="Search Requests"    value={latest_run_details.acquisition?.search_requests_attempted ?? '—'} mono />
                <DataRow label="Challenge Blocked"  value={latest_run_details.acquisition?.challenge_encountered ? 'Yes' : 'No'} />
              </ModuleCard>

              {/* Classification */}
              <ModuleCard icon={Activity} title="Classification">
                <DataRow label="Classified"         value={latest_run_details.classification?.summary?.classified ?? '—'} mono />
                <DataRow label="Deduplicated"        value={latest_run_details.classification?.summary?.description_duplicates_removed ?? '—'} mono />
                <DataRow label="Pre-filter Rejected" value={latest_run_details.classification?.rejected_count ?? '—'} mono />
              </ModuleCard>

              {/* Selection */}
              <ModuleCard icon={Activity} title="Selection &amp; Routing">
                <DataRow label="AI Scored"        value={latest_run_details.selection?.ranked ?? '—'} mono />
                <DataRow label="Routing Eligible" value={latest_run_details.selection?.hard_gate_eligible ?? '—'} mono />
                <DataRow label="Routing Blocked"  value={latest_run_details.selection?.hard_gate_rejected ?? '—'} mono />
              </ModuleCard>

              {/* Application */}
              <ModuleCard icon={Activity} title="Application">
                <DataRow label="Submitted (Live)"   value={<span className="text-healthy font-semibold">{latest_run_details.application?.submitted ?? '—'}</span>} />
                <DataRow label="Dry Run Skipped"    value={latest_run_details.application?.dry_run_skipped ?? '—'} mono />
                <DataRow label="Sent to Review"     value={<span className="text-pending font-semibold">{latest_run_details.application?.manual_review ?? '—'}</span>} />
                <DataRow label="Failed"             value={
                  (latest_run_details.application?.failed ?? 0) > 0
                    ? <span className="text-failed font-semibold">{latest_run_details.application?.failed}</span>
                    : '0'
                } />
              </ModuleCard>
            </div>

            {/* Errors */}
            {latest_run_details.errors?.length > 0 && (
              <div className="border border-failed/40 rounded-md bg-failed/5 p-4">
                <p className="text-[10px] font-semibold text-failed uppercase tracking-wider mb-3">Runtime Errors</p>
                <ul className="space-y-1 text-xs text-failed font-mono">
                  {latest_run_details.errors.map((err: string, i: number) => (
                    <li key={i} className="flex gap-2 items-start">
                      <span className="shrink-0 opacity-60">•</span>
                      <span>{err}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
