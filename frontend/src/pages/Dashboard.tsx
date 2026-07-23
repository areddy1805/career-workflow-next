import { useQuery } from '@tanstack/react-query';
import { fetchDashboard } from '@/lib/api';
import { StatusBadge } from '@/components/StatusBadge';
import { RelativeTime } from '@/components/RelativeTime';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';
import {
  Briefcase, CheckCircle2, TrendingUp, Globe, Activity, Clock,
  AlertCircle, CheckCircle, Play, ArrowRight, Cpu,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';

// ─── Lifecycle label map ──────────────────────────────────────────────────────
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

// ─── Metric Strip ─────────────────────────────────────────────────────────────

function MetricStrip({
  totalJobs,
  totalApplied,
  applicationRate,
  latestRun,
}: {
  totalJobs: number;
  totalApplied: number;
  applicationRate: string;
  latestRun: any;
}) {
  const navigate = useNavigate();

  return (
    <div className="flex items-stretch border border-border/50 rounded-lg bg-card overflow-hidden divide-x divide-border/50">
      {/* Total Jobs */}
      <button
        className="flex flex-col gap-1 px-5 py-4 hover:bg-secondary/40 transition-colors text-left flex-1"
        onClick={() => navigate('/jobs')}
        aria-label="View all jobs"
      >
        <span className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
          <Briefcase className="w-3 h-3" />
          Jobs Discovered
        </span>
        <span className="text-2xl font-bold tracking-tight tabular-nums">{totalJobs.toLocaleString()}</span>
      </button>

      {/* Applied */}
      <button
        className="flex flex-col gap-1 px-5 py-4 hover:bg-secondary/40 transition-colors text-left flex-1"
        onClick={() => navigate('/jobs')}
        aria-label="View applied jobs"
      >
        <span className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
          <CheckCircle2 className="w-3 h-3" />
          Applied
        </span>
        <span className="text-2xl font-bold tracking-tight tabular-nums text-emerald-500">{totalApplied.toLocaleString()}</span>
      </button>

      {/* Conversion Rate */}
      <div className="flex flex-col gap-1 px-5 py-4 flex-1">
        <span className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
          <TrendingUp className="w-3 h-3" />
          Conversion Rate
        </span>
        <span className="text-2xl font-bold tracking-tight tabular-nums">{applicationRate}%</span>
      </div>

      {/* Latest Run */}
      <button
        className="flex flex-col gap-1 px-5 py-4 hover:bg-secondary/40 transition-colors text-left flex-1"
        onClick={() => navigate('/runs')}
        aria-label="View run history"
      >
        <span className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
          <Play className="w-3 h-3" />
          Latest Run
        </span>
        {latestRun?.run_id ? (
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold font-mono tabular-nums">
              <RelativeTime date={latestRun.started_at} />
            </span>
            <StatusBadge status={latestRun.status ?? 'UNKNOWN'} />
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">No runs yet</span>
        )}
      </button>
    </div>
  );
}

// ─── System Status Bar ────────────────────────────────────────────────────────

function SystemStatusBar({ health }: { health: any }) {
  if (!health) return null;
  const status = health.status ?? 'UNKNOWN';
  const isHealthy = status === 'HEALTHY';
  const isWarning = status === 'WARNING';

  return (
    <div className={cn(
      'flex items-center gap-3 px-4 py-2.5 rounded-lg border text-xs',
      isHealthy ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-600 dark:text-emerald-400'
        : isWarning ? 'bg-amber-500/5 border-amber-500/20 text-amber-600 dark:text-amber-400'
        : 'bg-red-500/5 border-red-500/20 text-red-600 dark:text-red-400'
    )}>
      {isHealthy
        ? <CheckCircle className="w-3.5 h-3.5 shrink-0" />
        : <AlertCircle className="w-3.5 h-3.5 shrink-0" />}
      <span className="font-semibold">System {status}</span>
      <span className="text-current/60 ml-auto flex items-center gap-3">
        <span>Scheduler: {health.scheduler_running ? 'Running' : 'Stopped'}</span>
        <span>Pipeline: {health.pipeline_running ? 'Active' : 'Idle'}</span>
        {health.disk_usage_pct != null && (
          <span>Disk: {health.disk_usage_pct}%</span>
        )}
      </span>
    </div>
  );
}

// ─── Pipeline Stage Progress ──────────────────────────────────────────────────

function PipelineProgress({ latestRun }: { latestRun: any }) {
  if (!latestRun?.run_id) return null;

  return (
    <div className="bg-card border border-border/50 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
        <div className="flex items-center gap-2">
          <Cpu className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Last Run Progress
          </span>
        </div>
        <span className="text-[10px] font-mono text-muted-foreground/60 truncate max-w-[200px]">
          {latestRun.run_id}
        </span>
      </div>
      <div className="px-4 py-3 flex items-center gap-1 overflow-x-auto">
        {PIPELINE_STAGES.map((stage, idx) => {
          const raw = (latestRun?.stages?.[stage.key] ?? latestRun?.stage_results?.[stage.key] ?? 'PENDING').toUpperCase();
          const isSuccess = raw === 'SUCCESS';
          const isFailed  = raw === 'FAILED';
          const isRunning = raw === 'RUNNING' || raw === 'IN_PROGRESS';
          const isSkipped = raw === 'SKIPPED';

          return (
            <div key={stage.key} className="flex items-center gap-1 shrink-0">
              <div className={cn(
                'flex flex-col items-center gap-1 px-2.5 py-1.5 rounded text-[10px] font-medium border min-w-[72px] text-center',
                isSuccess ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                  : isFailed  ? 'bg-red-500/10 text-red-500 border-red-500/20'
                  : isRunning ? 'bg-blue-500/10 text-blue-400 border-blue-500/20 animate-pulse'
                  : isSkipped ? 'bg-zinc-500/8 text-zinc-500 border-zinc-500/20'
                  : 'bg-muted/40 text-muted-foreground border-border/30'
              )}>
                <span className="font-mono font-bold text-[9px]">{stage.label.slice(0,3).toUpperCase()}</span>
                <span className="text-[8px] opacity-70">{isSuccess ? '✓' : isFailed ? '✗' : isRunning ? '…' : '–'}</span>
              </div>
              {idx < PIPELINE_STAGES.length - 1 && (
                <ArrowRight className="w-3 h-3 text-border/50 shrink-0" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Provider Health ──────────────────────────────────────────────────────────

function ProviderHealth({ providerHealth }: { providerHealth: Record<string, any> }) {
  const providers = ['naukri', 'indeed', 'linkedin', 'google'];
  const NAMES: Record<string, string> = { naukri: 'Naukri', indeed: 'Indeed', linkedin: 'LinkedIn', google: 'Google Jobs' };

  return (
    <div className="bg-card border border-border/50 rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/40">
        <Globe className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Provider Health</span>
      </div>
      <div className="divide-y divide-border/30">
        {providers.map(id => {
          const h = providerHealth?.[id] ?? {};
          const status = (h.status ?? 'unknown').toLowerCase();
          const successPct = Math.round((h.success_rate ?? 0) * 100);

          return (
            <div key={id} className="flex items-center gap-4 px-4 py-2.5">
              <span className="text-xs font-semibold w-24 shrink-0">{NAMES[id]}</span>
              <StatusBadge status={status.toUpperCase()} />
              <div className="flex items-center gap-4 ml-auto text-[10px] text-muted-foreground font-mono">
                <span>{h.total_searches ?? 0} searches</span>
                <span className={successPct >= 90 ? 'text-emerald-500' : 'text-amber-500'}>{successPct}%</span>
                <span>{(h.average_latency_seconds ?? 0).toFixed(2)}s</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Activity Feed ────────────────────────────────────────────────────────────

function ActivityFeed({ latestRun, topCompanies, upcomingExecutions }: {
  latestRun: any;
  topCompanies: any[];
  upcomingExecutions: any[];
}) {
  // Build a synthetic activity list from available data
  const activities: Array<{ icon: React.ReactNode; label: string; time?: string; type: 'success' | 'info' | 'warning' | 'neutral' }> = [];

  if (latestRun?.run_id) {
    const stageCount = Object.values(latestRun.stages ?? latestRun.stage_results ?? {}).filter((s: any) => s.toUpperCase() === 'SUCCESS').length;
    if (stageCount > 0) {
      activities.push({ icon: <CheckCircle className="w-3.5 h-3.5" />, label: `${stageCount} pipeline stages completed`, time: latestRun.started_at, type: 'success' });
    }
    if (latestRun.status === 'FAILED') {
      activities.push({ icon: <AlertCircle className="w-3.5 h-3.5" />, label: 'Last run failed', time: latestRun.started_at, type: 'warning' });
    }
  }

  if (topCompanies?.length > 0) {
    activities.push({
      icon: <Briefcase className="w-3.5 h-3.5" />,
      label: `${topCompanies.slice(0, 3).map((c: any) => c.name ?? c.company).join(', ')} — top hiring companies`,
      type: 'info',
    });
  }

  if (upcomingExecutions?.length > 0) {
    activities.push({
      icon: <Clock className="w-3.5 h-3.5" />,
      label: `Next run scheduled: ${upcomingExecutions[0].task}`,
      time: upcomingExecutions[0].scheduled_for,
      type: 'neutral',
    });
  }

  if (activities.length === 0) {
    activities.push({ icon: <Activity className="w-3.5 h-3.5" />, label: 'No recent activity. Run the pipeline to get started.', type: 'neutral' });
  }

  const typeColors: Record<string, string> = {
    success: 'text-emerald-500',
    info:    'text-blue-400',
    warning: 'text-amber-500',
    neutral: 'text-muted-foreground',
  };

  return (
    <div className="bg-card border border-border/50 rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/40">
        <Activity className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Recent Activity</span>
      </div>
      <div className="divide-y divide-border/20">
        {activities.map((act, i) => (
          <div key={i} className="flex items-start gap-3 px-4 py-3">
            <span className={cn('shrink-0 mt-0.5', typeColors[act.type])}>
              {act.icon}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-foreground leading-relaxed">{act.label}</p>
              {act.time && (
                <p className="text-[10px] text-muted-foreground mt-0.5">
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

// ─── Pipeline Funnel Chart ────────────────────────────────────────────────────

function FunnelChart({ lifecycle }: { lifecycle: any[] }) {
  if (!lifecycle?.length) return null;

  return (
    <div className="bg-card border border-border/50 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-border/40">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Application Funnel</span>
      </div>
      <div className="p-4 h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={lifecycle} layout="vertical" margin={{ left: 16, right: 24, top: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
            <XAxis type="number" tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
            <YAxis
              dataKey="lifecycle_stage"
              type="category"
              width={80}
              tick={{ fontSize: 10, fill: 'hsl(var(--foreground))' }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ fill: 'hsl(var(--muted) / 0.4)' }}
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '6px',
                fontSize: '11px',
                color: 'hsl(var(--foreground))',
              }}
            />
            <Bar dataKey="count" fill="hsl(var(--chart-1))" radius={[0, 3, 3, 0]} maxBarSize={24} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function OverviewSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      <div className="h-6 w-32 bg-muted rounded" />
      <div className="h-[84px] bg-muted rounded-lg" />
      <div className="h-10 bg-muted rounded-lg" />
      <div className="grid grid-cols-2 gap-4">
        <div className="h-[220px] bg-muted rounded-lg" />
        <div className="h-[220px] bg-muted rounded-lg" />
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    refetchInterval: 30_000,
  });

  if (isLoading) return <OverviewSkeleton />;

  const {
    summary,
    lifecycle: rawLifecycle,
    latest_run,
    system_health,
    upcoming_executions,
    top_companies,
    provider_health,
  } = dashboard ?? {};

  const totalJobs      = summary?.total_jobs ?? 0;
  const totalApplied   = summary?.total_applied ?? 0;
  const applicationRate = totalJobs > 0 ? ((totalApplied / totalJobs) * 100).toFixed(1) : '0';

  const lifecycle = (rawLifecycle ?? []).map((d: any) => ({
    ...d,
    lifecycle_stage: LIFECYCLE_LABELS[d.lifecycle_stage] ?? d.lifecycle_stage,
  })).filter((d: any) => d.count > 0);

  return (
    <div className="h-full flex flex-col bg-background overflow-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Overview</h1>
          <p className="text-xs text-muted-foreground mt-0.5">System health, pipeline status, and application progress at a glance.</p>
        </div>
      </div>

      <div className="flex-1 p-6 space-y-5 max-w-[1600px]">

        {/* System Status — always first */}
        <SystemStatusBar health={system_health} />

        {/* Metric Strip */}
        <MetricStrip
          totalJobs={totalJobs}
          totalApplied={totalApplied}
          applicationRate={applicationRate}
          latestRun={latest_run}
        />

        {/* Pipeline Stage Progress */}
        <PipelineProgress latestRun={latest_run} />

        {/* Two-column: Funnel + Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          <div className="lg:col-span-3">
            <FunnelChart lifecycle={lifecycle} />
          </div>
          <div className="lg:col-span-2">
            <ActivityFeed
              latestRun={latest_run}
              topCompanies={top_companies ?? []}
              upcomingExecutions={upcoming_executions ?? []}
            />
          </div>
        </div>

        {/* Provider Health */}
        <ProviderHealth providerHealth={provider_health ?? {}} />

      </div>
    </div>
  );
}
