import React from 'react';
import { useDashboard } from '@/lib/hooks';
import { StatusBadge } from '@/components/operations/StatusBadge';
import { MetricCard, MetricGrid } from '@/components/operations/MetricCard';
import { SectionTitle } from '@/components/operations/SectionTitle';
import { RelativeTime } from '@/components/RelativeTime';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { Briefcase, CheckCircle2, TrendingUp, Play, Cpu, CheckCircle, AlertCircle, Clock, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';

// ─── Lifecycle map ────────────────────────────────────────────────────────────
const LIFECYCLE_LABELS: Record<string, string> = {
  UNKNOWN:     'Acquired',
  SUBMITTED:   'Submitted',
  VIEWED:      'Viewed',
  SHORTLISTED: 'Shortlisted',
  INTERVIEW:   'Interview',
  REJECTED:    'Rejected',
  OFFER:       'Offer',
};

const PIPELINE_STAGES = [
  { key: 'preflight',      label: 'Preflight'       },
  { key: 'acquisition',   label: 'Acquisition'     },
  { key: 'classification',label: 'Classification'  },
  { key: 'selection',     label: 'Selection'       },
  { key: 'application',   label: 'Application'     },
  { key: 'reconciliation',label: 'Reconciliation'  },
  { key: 'strategy',      label: 'Strategy'        },
  { key: 'report',        label: 'Report'          },
];

// ─── Pipeline Progress ───────────────────────────────────────────────────────

function PipelineTracker({ latestRun }: { latestRun: any }) {
  if (!latestRun?.run_id) return null;

  return (
    <div className="bg-card border border-border rounded-md shadow-card mb-6">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-semibold text-foreground uppercase tracking-wider">
            Pipeline Execution
          </span>
        </div>
        <span className="text-[10px] font-mono text-muted-foreground truncate">
          Run ID: {latestRun.run_id}
        </span>
      </div>
      <div className="px-4 py-4 flex items-center justify-between overflow-x-auto gap-2">
        {PIPELINE_STAGES.map((stage, idx) => {
          const raw = (latestRun?.stages?.[stage.key] ?? latestRun?.stage_results?.[stage.key] ?? 'PENDING').toUpperCase();
          const isSuccess = raw === 'SUCCESS';
          const isFailed  = raw === 'FAILED';
          const isRunning = raw === 'RUNNING' || raw === 'IN_PROGRESS';
          // const isPending = raw === 'PENDING' || raw === 'SKIPPED';

          let icon = <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30" />;
          if (isSuccess) icon = <CheckCircle2 className="w-3 h-3 text-emerald-500" />;
          if (isFailed) icon = <AlertCircle className="w-3 h-3 text-red-500" />;
          if (isRunning) icon = <span className="w-1.5 h-1.5 rounded-full bg-blue-500 pulse-green" />;

          return (
            <React.Fragment key={stage.key}>
              <div className="flex flex-col items-center gap-2 min-w-[72px]">
                <div className={cn(
                  "w-8 h-8 rounded-full border flex items-center justify-center shrink-0 transition-colors",
                  isSuccess ? "border-emerald-500/30 bg-emerald-500/10" :
                  isFailed ? "border-red-500/30 bg-red-500/10" :
                  isRunning ? "border-blue-500/30 bg-blue-500/10" :
                  "border-border bg-muted/30"
                )}>
                  {icon}
                </div>
                <span className={cn(
                  "text-[10px] font-medium tracking-wide uppercase",
                  isSuccess ? "text-emerald-600 dark:text-emerald-400" :
                  isFailed ? "text-red-600 dark:text-red-400" :
                  isRunning ? "text-blue-600 dark:text-blue-400 font-bold" :
                  "text-muted-foreground"
                )}>
                  {stage.label}
                </span>
              </div>
              {idx < PIPELINE_STAGES.length - 1 && (
                <div className="flex-1 h-[1px] bg-border mx-2 min-w-[16px]" />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

// ─── Funnel Chart ────────────────────────────────────────────────────────────

function FunnelChart({ lifecycle }: { lifecycle: any[] }) {
  if (!lifecycle?.length) return (
    <div className="h-[240px] flex items-center justify-center text-muted-foreground text-sm border border-dashed rounded-md">
      No funnel data available
    </div>
  );

  return (
    <div className="bg-card border border-border rounded-md shadow-card">
      <div className="px-4 py-3 border-b border-border/50">
        <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Application Funnel</span>
      </div>
      <div className="p-4 h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={lifecycle} layout="vertical" margin={{ left: 16, right: 24, top: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
            <XAxis type="number" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
            <YAxis
              dataKey="lifecycle_stage"
              type="category"
              width={80}
              tick={{ fontSize: 11, fill: 'hsl(var(--foreground))', fontWeight: 500 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ fill: 'hsl(var(--muted) / 0.4)' }}
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '6px',
                fontSize: '12px',
                color: 'hsl(var(--foreground))',
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
              }}
            />
            <Bar dataKey="count" fill="hsl(var(--foreground))" radius={[0, 2, 2, 0]} maxBarSize={20} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Activity Feed ───────────────────────────────────────────────────────────

function ActivityFeed({ latestRun, upcomingExecutions }: { latestRun: any; upcomingExecutions: any[] }) {
  const activities: Array<{ icon: React.ReactNode; label: string; time?: string; type: 'success' | 'warning' | 'neutral' }> = [];

  if (latestRun?.run_id) {
    if (latestRun.status === 'SUCCESS' || latestRun.status === 'COMPLETED') {
      activities.push({ icon: <CheckCircle className="w-3.5 h-3.5" />, label: `Run ${latestRun.run_id} completed successfully`, time: latestRun.started_at, type: 'success' });
    } else if (latestRun.status === 'FAILED') {
      activities.push({ icon: <AlertCircle className="w-3.5 h-3.5" />, label: `Run ${latestRun.run_id} failed`, time: latestRun.started_at, type: 'warning' });
    } else {
      activities.push({ icon: <Play className="w-3.5 h-3.5" />, label: `Run ${latestRun.run_id} is active`, time: latestRun.started_at, type: 'neutral' });
    }
  }

  if (upcomingExecutions?.length > 0) {
    activities.push({
      icon: <Clock className="w-3.5 h-3.5" />,
      label: `Next scheduled execution: ${upcomingExecutions[0].task}`,
      time: upcomingExecutions[0].scheduled_for,
      type: 'neutral',
    });
  }

  if (activities.length === 0) {
    activities.push({ icon: <Activity className="w-3.5 h-3.5" />, label: 'System idle. Awaiting operational input.', type: 'neutral' });
  }

  const typeColors = {
    success: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
    warning: 'text-amber-500 bg-amber-500/10 border-amber-500/20',
    neutral: 'text-muted-foreground bg-muted border-border',
  };

  return (
    <div className="bg-card border border-border rounded-md shadow-card">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/50">
        <Activity className="w-4 h-4 text-muted-foreground" />
        <span className="text-xs font-semibold text-foreground uppercase tracking-wider">Operational Log</span>
      </div>
      <div className="divide-y divide-border/50">
        {activities.map((act, i) => (
          <div key={i} className="flex items-start gap-3 px-4 py-3 hover:bg-muted/30 transition-colors">
            <div className={cn("mt-0.5 w-6 h-6 rounded flex items-center justify-center shrink-0 border", typeColors[act.type])}>
              {act.icon}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] text-foreground font-medium">{act.label}</p>
              {act.time && (
                <p className="text-[11px] text-muted-foreground font-mono mt-0.5">
                  <RelativeTime date={act.time} />
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Skeletons ────────────────────────────────────────────────────────────────

function OverviewSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-[120px] bg-muted/50 rounded-md" />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1,2,3,4].map(i => <div key={i} className="h-24 bg-muted/50 rounded-md" />)}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-[300px] bg-muted/50 rounded-md" />
        <div className="h-[300px] bg-muted/50 rounded-md" />
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { data: dashboard, isLoading } = useDashboard();
  

  if (isLoading) return <OverviewSkeleton />;

  const {
    lifecycle_metrics,
    summary,
    lifecycle: rawLifecycle,
    latest_run,
    system_health,
    upcoming_executions,
  } = dashboard ?? {};

  // Prefer lifecycle-derived metrics (canonical source of truth)
  const lc = lifecycle_metrics ?? {};
  const totalJobs = lc.acquired ?? summary?.total_jobs ?? 0;
  const totalSubmitted = lc.submitted ?? summary?.total_applied ?? 0;
  const totalRouted = lc.routed ?? 0;
  const latestRun = latest_run?.run_id ? <RelativeTime date={latest_run.started_at} /> : 'None';

  // Build lifecycle distribution from canonical lifecycle metrics
  const PIPELINE_LIFECYCLE = [
    { lifecycle_stage: 'Acquired', count: lc.acquired ?? 0 },
    { lifecycle_stage: 'Pre-App Rejected', count: lc.pre_app_rejected ?? 0 },
    { lifecycle_stage: 'Selected', count: lc.selected ?? 0 },
    { lifecycle_stage: 'Routed', count: lc.routed ?? 0 },
    { lifecycle_stage: 'Submitted', count: lc.submitted ?? 0 },
    { lifecycle_stage: 'Failed', count: lc.application_failed ?? 0 },
    { lifecycle_stage: 'Deferred', count: lc.deferred ?? 0 },
  ].filter(d => d.count > 0);

  // Fall back to legacy lifecycle distribution if no metrics available
  const lifecycle = !lc.acquired && (rawLifecycle ?? []).length > 0
    ? (rawLifecycle ?? []).map((d: any) => ({
        ...d,
        lifecycle_stage: LIFECYCLE_LABELS[d.lifecycle_stage] ?? d.lifecycle_stage,
      })).filter((d: any) => d.count > 0)
    : PIPELINE_LIFECYCLE;

  const sysStatus = system_health?.status === 'HEALTHY' ? 'success' : system_health?.status === 'WARNING' ? 'warning' : 'error';

  return (
    <div className="flex flex-col h-full animate-in fade-in duration-300">
      <SectionTitle 
        title="Overview" 
        subtitle="System health, pipeline status, and application metrics."
        action={
          <StatusBadge 
            status={sysStatus} 
            label={`System ${system_health?.status ?? 'Unknown'}`} 
            pulse={sysStatus === 'success'}
          />
        }
      />

      <PipelineTracker latestRun={latest_run} />

      <MetricGrid className="mb-6">
        <MetricCard
          title="Jobs Acquired"
          value={totalJobs.toLocaleString()}
          icon={<Briefcase className="w-4 h-4" />}
          className="cursor-pointer hover:border-foreground/30 transition-colors"
        />
        <MetricCard
          title="Submitted"
          value={totalSubmitted.toLocaleString()}
          icon={<CheckCircle2 className="w-4 h-4" />}
          className="cursor-pointer hover:border-foreground/30 transition-colors"
        />
        <MetricCard
          title="Routed"
          value={totalRouted.toLocaleString()}
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <MetricCard
          title="Latest Run"
          value={latestRun}
          icon={<Play className="w-4 h-4" />}
          className="cursor-pointer hover:border-foreground/30 transition-colors"
        />
      </MetricGrid>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-8">
        <FunnelChart lifecycle={lifecycle} />
        <ActivityFeed latestRun={latest_run} upcomingExecutions={upcoming_executions ?? []} />
      </div>
    </div>
  );
}
