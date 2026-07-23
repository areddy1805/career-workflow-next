import { useQuery } from '@tanstack/react-query';
import { fetchRuns, fetchDashboard } from '@/lib/api';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
  Legend,
  Cell,
  ReferenceLine,
} from 'recharts';
import { TrendingUp, Activity, CheckCircle2, Layers, Target } from 'lucide-react';

// ─── Label Maps ──────────────────────────────────────────────────────────────

const LIFECYCLE_LABELS: Record<string, string> = {
  UNKNOWN: 'Acquired',
  SUBMITTED: 'Submitted',
  VIEWED: 'Viewed',
  SHORTLISTED: 'Shortlisted',
  INTERVIEW: 'Interview',
  REJECTED: 'Rejected',
  OFFER: 'Offer',
};

// All chart colors derive from CSS tokens — adapts correctly to light/dark mode
const LIFECYCLE_COLORS: Record<string, string> = {
  Acquired:    'hsl(var(--chart-1))',
  Submitted:   'hsl(var(--chart-2))',
  Viewed:      'hsl(var(--chart-3))',
  Shortlisted: 'hsl(var(--chart-4))',
  Interview:   'hsl(var(--chart-6))',
  Rejected:    'hsl(var(--chart-5))',
  Offer:       'hsl(var(--chart-2))',
};

const TOOLTIP_STYLE = {
  backgroundColor: 'hsl(var(--card))',
  border: '1px solid hsl(var(--border))',
  borderRadius: '6px',
  fontSize: '11px',
  color: 'hsl(var(--foreground))',
};

// ─── KPI Card ────────────────────────────────────────────────────────────────

function KpiCard({
  label, value, sub, icon: Icon, color = 'text-primary',
}: { label: string; value: string | number; sub?: string; icon: any; color?: string }) {
  return (
    <div className="bg-card border border-border/50 rounded-lg p-4 flex items-start gap-3">
      <div className={`mt-0.5 p-2 rounded-md bg-current/10 ${color}`}>
        <Icon className="w-3.5 h-3.5" />
      </div>
      <div className="min-w-0">
        <p className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground mb-0.5">{label}</p>
        <p className={`text-2xl font-bold tracking-tight ${color}`}>{value}</p>
        {sub && <p className="text-[10px] text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function Analytics() {
  const { data: runs = [], isLoading: runsLoading } = useQuery({
    queryKey: ['runs'],
    queryFn: fetchRuns,
  });

  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
  });

  const isLoading = runsLoading || dashLoading;

  if (isLoading) {
    return (
      <div className="h-full flex flex-col bg-background p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-muted w-1/4 rounded" />
          <div className="grid grid-cols-4 gap-3">
            {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-muted rounded-lg" />)}
          </div>
          <div className="grid grid-cols-2 gap-4">
            {[1, 2].map(i => <div key={i} className="h-72 bg-muted rounded-lg" />)}
          </div>
        </div>
      </div>
    );
  }

  // ── Lifecycle data with friendly labels ─────────────────────────────────────
  const { lifecycle: rawLifecycle, summary } = dashboard || {};

  const lifecycle = (rawLifecycle || [])
    .map((d: any) => ({
      ...d,
      lifecycle_stage: LIFECYCLE_LABELS[d.lifecycle_stage] ?? d.lifecycle_stage,
    }))
    .filter((d: any) => d.count > 0); // hide zero-count stages to reduce noise

  // ── Run trend data ────────────────────────────────────────────────────────
  const recentRuns = [...(runs as any[])].reverse().slice(-20); // oldest→newest

  const yieldData = recentRuns.map((run: any, i: number) => ({
    idx: i + 1,
    Acquired: run.acquired ?? 0,
    Classified: run.classified ?? 0,
    Selected: run.selected ?? 0,
  }));

  const outcomeData = recentRuns.map((run: any, i: number) => ({
    idx: i + 1,
    Submitted: run.submitted ?? 0,
    ManualReview: run.manual_review ?? 0,
    Failed: run.failed ?? 0,
    DryRun: run.dry_run_skipped ?? 0,
  }));

  // ── KPI derivations ───────────────────────────────────────────────────────
  const totalJobs = summary?.total_jobs ?? 0;
  const totalApplied = summary?.total_applied ?? 0;
  const totalRuns = (runs as any[]).length;
  const successRuns = (runs as any[]).filter((r: any) => r.status === 'SUCCESS').length;
  const successRate = totalRuns > 0 ? Math.round((successRuns / totalRuns) * 100) : 0;

  const avgAcquired =
    recentRuns.length > 0
      ? Math.round(recentRuns.reduce((a: number, r: any) => a + (r.acquired ?? 0), 0) / recentRuns.length)
      : 0;

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      {/* Page Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Analytics</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Pipeline performance, application lifecycle, and outcome trends.
            <span className="ml-1 text-muted-foreground/60">{totalRuns} runs · {totalJobs.toLocaleString()} jobs</span>
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-5 space-y-5">
        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KpiCard label="Total Jobs" value={totalJobs.toLocaleString()} sub="ingested from all providers" icon={Layers} color="text-primary" />
          <KpiCard label="Total Applied" value={totalApplied.toLocaleString()} sub="across all runs" icon={CheckCircle2} color="text-green-500" />
          <KpiCard label="Run Success Rate" value={`${successRate}%`} sub={`${successRuns} of ${totalRuns} runs`} icon={Target} color="text-blue-400" />
          <KpiCard label="Avg Jobs / Run" value={avgAcquired} sub="acquired per run (last 20)" icon={Activity} color="text-amber-400" />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
          {/* Lifecycle Distribution — 2 cols */}
          <div className="xl:col-span-2 bg-card border border-border/50 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground">Application Lifecycle Distribution</span>
            </div>
            {lifecycle.length > 0 ? (
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={lifecycle}
                    layout="vertical"
                    margin={{ left: 8, right: 24, top: 4, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                      tickLine={false}
                      axisLine={false}
                    />
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
                      contentStyle={TOOLTIP_STYLE}
                      formatter={(value: any, _: any, props: any) => [value.toLocaleString(), props.payload.lifecycle_stage]}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={26}>
                      {lifecycle.map((entry: any) => (
                        <Cell
                          key={entry.lifecycle_stage}
                          fill={LIFECYCLE_COLORS[entry.lifecycle_stage] ?? 'hsl(var(--primary))'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[260px] flex items-center justify-center text-muted-foreground text-xs">No lifecycle data.</div>
            )}
          </div>

          {/* Pipeline Yield Trend — 3 cols */}
          <div className="xl:col-span-3 bg-card border border-border/50 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-3 h-3 text-muted-foreground" />
              <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground">Pipeline Yield Trend — Last {recentRuns.length} Runs</span>
            </div>
            {yieldData.length > 0 ? (
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={yieldData} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="idx"
                      tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                      tickLine={false}
                      axisLine={false}
                      label={{ value: 'Run (oldest → newest)', position: 'insideBottom', offset: -2, fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    />
                    <YAxis tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: '10px', paddingTop: '8px' }} />
                    <Line type="monotone" dataKey="Acquired" stroke="hsl(var(--chart-1))" strokeWidth={2} dot={false} activeDot={{ r: 3 }} />
                    <Line type="monotone" dataKey="Classified" stroke="hsl(var(--chart-3))" strokeWidth={2} dot={false} activeDot={{ r: 3 }} />
                    <Line type="monotone" dataKey="Selected" stroke="hsl(var(--chart-2))" strokeWidth={2} dot={false} activeDot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[260px] flex items-center justify-center text-muted-foreground text-xs">No run data.</div>
            )}
          </div>
        </div>

        {/* Outcomes Row */}
        <div className="bg-card border border-border/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[9px] uppercase tracking-wider font-semibold text-muted-foreground">Application Outcomes per Run — Last {recentRuns.length} Runs</span>
          </div>
          {outcomeData.length > 0 ? (
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={outcomeData} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="idx" tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend iconSize={8} wrapperStyle={{ fontSize: '10px' }} />
                  <ReferenceLine y={0} stroke="hsl(var(--border))" />
                  <Bar dataKey="Submitted" fill="hsl(var(--chart-2))" radius={[2, 2, 0, 0]} maxBarSize={18} />
                  <Bar dataKey="ManualReview" fill="hsl(var(--chart-4))" radius={[2, 2, 0, 0]} maxBarSize={18} />
                  <Bar dataKey="Failed" fill="hsl(var(--chart-5))" radius={[2, 2, 0, 0]} maxBarSize={18} />
                  <Bar dataKey="DryRun" fill="hsl(var(--muted-foreground) / 0.4)" radius={[2, 2, 0, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground text-xs">No outcome data.</div>
          )}
        </div>
      </div>
    </div>
  );
}
