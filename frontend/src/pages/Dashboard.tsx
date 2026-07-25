import { useViewModel } from '@/lib/hooks';
import {
  Activity, Clock,
  BrainCircuit, Zap, ScrollText, AlertTriangle, XCircle, LayoutDashboard,
  Terminal, Server, AlertCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

// --- Linear/Vercel Aesthetic Components ---

function Panel({ title, icon: Icon, children, className, action }: any) {
  return (
    <div className={cn(
      "bg-[#0A0A0A] border border-white/[0.08] rounded-xl flex flex-col relative overflow-hidden transition-all duration-300 hover:border-white/[0.12]", 
      className
    )}>
      {/* Subtle top gradient glow effect on hover could go here */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.04] shrink-0">
        <div className="flex items-center gap-2.5">
          {Icon && <Icon className="w-4 h-4 text-white/40" />}
          <span className="text-[13px] font-medium text-white/70 tracking-wide">{title}</span>
        </div>
        {action && <div>{action}</div>}
      </div>
      <div className="p-5 flex-1 flex flex-col overflow-auto">
        {children}
      </div>
    </div>
  );
}

function MetricRow({ label, value, highlight, isStatus, statusColor }: { label: string, value: ReactNode, highlight?: boolean, isStatus?: boolean, statusColor?: string }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-white/[0.03] last:border-0 group">
      <span className="text-[13px] text-white/50 group-hover:text-white/70 transition-colors">{label}</span>
      <div className="flex items-center gap-2">
        {isStatus && statusColor && (
          <div className={cn("w-1.5 h-1.5 rounded-full", statusColor)} />
        )}
        <span className={cn(
          "text-[13px] font-medium font-mono text-white/90", 
          highlight && "text-emerald-400"
        )}>
          {value}
        </span>
      </div>
    </div>
  );
}

// --- Specific Panels ---

function HeaderPanel({ header, version }: { header: any, version: string }) {
  const isRunning = header.run_status?.toLowerCase() === 'running';
  const isSuccess = header.run_status?.toLowerCase() === 'completed';
  const isFailed = header.run_status?.toLowerCase() === 'failed';
  
  const statusColor = isRunning ? 'bg-blue-500' : isSuccess ? 'bg-emerald-500' : isFailed ? 'bg-red-500' : 'bg-white/20';
  const statusText = isRunning ? 'text-blue-400' : isSuccess ? 'text-emerald-400' : isFailed ? 'text-red-400' : 'text-white/40';

  return (
    <Panel title="Execution Context" icon={Terminal} className="col-span-2 md:col-span-1">
      <div className="flex flex-col h-full justify-between gap-6">
        <div>
          <div className="flex justify-between items-start mb-1">
            <h2 className="text-xl font-semibold text-white tracking-tight">{header.title}</h2>
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.05]">
              <div className={cn("w-1.5 h-1.5 rounded-full animate-pulse", statusColor)} />
              <span className={cn("text-xs font-medium uppercase tracking-wider", statusText)}>{header.run_status}</span>
            </div>
          </div>
          <p className="text-sm text-white/40">Version {version}</p>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white/[0.02] rounded-lg p-3 border border-white/[0.04]">
            <p className="text-[11px] uppercase tracking-wider text-white/40 mb-1">Run ID</p>
            <p className="text-xs font-mono text-white/80 truncate">{header.run_id}</p>
          </div>
          <div className="bg-white/[0.02] rounded-lg p-3 border border-white/[0.04]">
            <p className="text-[11px] uppercase tracking-wider text-white/40 mb-1">Profile</p>
            <p className="text-xs text-white/80 font-medium truncate">{header.profile}</p>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function HealthPanel({ health }: { health: any }) {
  const getStatus = (s: string) => {
    const sl = s.toLowerCase();
    if (sl === 'healthy' || sl === 'success' || sl === 'active') return { color: 'bg-emerald-500', text: 'Operational' };
    return { color: 'bg-red-500', text: s.charAt(0).toUpperCase() + s.slice(1) };
  };

  return (
    <Panel title="System Health" icon={Server} className="col-span-2 md:col-span-1">
      <div className="space-y-1">
        {Object.entries(health.providers || {}).map(([provider, details]: any) => {
          const st = getStatus(details.status);
          return (
            <MetricRow 
              key={provider} 
              label={provider.charAt(0).toUpperCase() + provider.slice(1)} 
              value={st.text} 
              isStatus 
              statusColor={st.color} 
            />
          );
        })}
        <MetricRow label="Browser Agent" value={getStatus(health.browser.status).text} isStatus statusColor={getStatus(health.browser.status).color} />
        <MetricRow label="Local Database" value={getStatus(health.sqlite.status).text} isStatus statusColor={getStatus(health.sqlite.status).color} />
        <MetricRow label="Artifact Store" value={getStatus(health.artifacts.status).text} isStatus statusColor={getStatus(health.artifacts.status).color} />
      </div>
    </Panel>
  );
}

function PipelinePanel({ progress }: { progress: any }) {
  const percent = progress.total_stages > 0 ? Math.floor((progress.completed_stages / progress.total_stages) * 100) : 0;
  
  return (
    <Panel title="Pipeline Activity" icon={Activity} className="col-span-2 md:col-span-1">
      <div className="mb-6">
        <div className="flex justify-between items-end mb-3">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-white/40 mb-1">Current Stage</p>
            <p className="text-sm font-medium text-white/90">{progress.current_stage || "IDLE"}</p>
          </div>
          <span className="text-2xl font-light tracking-tighter text-white">{percent}%</span>
        </div>
        <div className="w-full bg-white/[0.04] h-1.5 rounded-full overflow-hidden">
          <div 
            className="bg-white h-full transition-all duration-700 ease-out" 
            style={{ width: `${percent}%`, boxShadow: '0 0 10px rgba(255,255,255,0.5)' }}
          />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 mt-auto">
        <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3 text-center">
          <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Acquired</p>
          <p className="text-lg font-mono text-white/90">{progress.jobs_acquired}</p>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3 text-center">
          <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Classified</p>
          <p className="text-lg font-mono text-white/90">{progress.jobs_classified}</p>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3 text-center">
          <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Applied</p>
          <p className="text-lg font-mono text-emerald-400">{progress.jobs_applied}</p>
        </div>
      </div>
    </Panel>
  );
}

function InferencePanel({ inference }: { inference: any }) {
  return (
    <Panel title="Inference Metrics" icon={BrainCircuit} className="col-span-2 md:col-span-1">
      <div className="space-y-1">
        <MetricRow label="Total Requests" value={inference.requests} />
        <MetricRow label="Tokens Processed" value={inference.tokens.toLocaleString()} />
        <MetricRow label="Compute Cost" value={`$${inference.cost.toFixed(4)}`} highlight />
        <MetricRow label="Average Latency" value={`${inference.average_latency.toFixed(2)}s`} />
        <MetricRow label="Provider Fallbacks" value={inference.fallbacks} />
      </div>
    </Panel>
  );
}

function TimelinePanel({ timeline }: { timeline: any[] }) {
  return (
    <Panel title="Event Timeline" icon={Clock} className="col-span-2 md:col-span-1 min-h-[280px]">
      <div className="space-y-4">
        {timeline.slice(-8).reverse().map((event: any, i: number) => {
          const time = event.timestamp.split('T')[1].substring(0, 8);
          const isSuccess = event.level === 'success';
          const isError = event.level === 'error';
          
          return (
            <div key={i} className="flex gap-4 group">
              <div className="flex flex-col items-center mt-1">
                <div className={cn(
                  "w-2 h-2 rounded-full",
                  isSuccess ? "bg-emerald-500" : isError ? "bg-red-500" : "bg-white/20"
                )} />
                {i !== Math.min(timeline.length, 8) - 1 && (
                  <div className="w-[1px] h-full bg-white/[0.08] mt-2 group-hover:bg-white/[0.15] transition-colors" />
                )}
              </div>
              <div className="flex flex-col pb-2">
                <span className={cn(
                  "text-[13px] leading-tight",
                  isSuccess ? "text-emerald-400" : isError ? "text-red-400" : "text-white/80"
                )}>
                  {event.message}
                </span>
                <span className="text-[11px] text-white/30 font-mono mt-1">{time}</span>
              </div>
            </div>
          );
        })}
        {timeline.length === 0 && (
          <div className="h-full flex items-center justify-center text-[13px] text-white/30">
            Waiting for events...
          </div>
        )}
      </div>
    </Panel>
  );
}

function EfficiencyPanel({ efficiency }: { efficiency: any }) {
  return (
    <Panel title="Pipeline Efficiency" icon={Zap} className="col-span-2 md:col-span-1">
      <div className="space-y-1">
        <MetricRow label="Deterministic Rejections" value={efficiency.deterministic_rejections} />
        <MetricRow label="Semantic Cache Hits" value={efficiency.semantic_reuse} />
        <MetricRow label="LLM Avoidance Rate" value={`${(efficiency.llm_avoidance_rate || 0).toFixed(1)}%`} highlight />
      </div>
      
      {/* Visual Avoidance Bar */}
      <div className="mt-6 pt-4 border-t border-white/[0.04]">
        <div className="flex justify-between items-center mb-2">
          <span className="text-[11px] uppercase tracking-wider text-white/40">Resource Optimization</span>
        </div>
        <div className="w-full bg-white/[0.04] h-2 rounded-full overflow-hidden flex">
          <div className="bg-emerald-500 h-full" style={{ width: `${efficiency.llm_avoidance_rate || 0}%` }} />
          <div className="bg-blue-500/50 h-full" style={{ width: `${100 - (efficiency.llm_avoidance_rate || 0)}%` }} />
        </div>
        <div className="flex justify-between mt-2 text-[10px] text-white/30 font-mono">
          <span>{efficiency.llm_avoidance_rate?.toFixed(0)}% Saved</span>
          <span>Compute</span>
        </div>
      </div>
    </Panel>
  );
}

function NotificationsPanel({ notifications }: { notifications: any[] }) {
  return (
    <Panel title="Active Alerts" icon={AlertTriangle} className="col-span-2 md:col-span-1 min-h-[220px]">
      <div className="space-y-3">
        {notifications.slice(-5).map((event: any, i: number) => {
          const time = event.timestamp.split('T')[1].substring(0, 8);
          return (
            <div key={i} className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 flex gap-3 items-start">
              <AlertCircle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <div className="flex flex-col">
                <span className="text-[13px] text-amber-200/90 leading-tight">{event.message}</span>
                <span className="text-[10px] text-amber-500/50 font-mono mt-1.5">{time}</span>
              </div>
            </div>
          );
        })}
        {notifications.length === 0 && (
          <div className="h-full flex items-center justify-center text-[13px] text-white/30">
            No active alerts.
          </div>
        )}
      </div>
    </Panel>
  );
}

function DecisionSummaryPanel({ summary }: { summary: any }) {
  return (
    <Panel title="Outcome Ledger" icon={ScrollText} className="col-span-2 md:col-span-1">
      <div className="space-y-1">
        <MetricRow label="Jobs Discovered" value={summary.jobs_found} />
        <MetricRow label="Already Processed" value={summary.already_processed} />
        <MetricRow label="New Candidates" value={summary.new_candidates} />
        <MetricRow label="Description Duplicates" value={summary.description_duplicates} />
        <MetricRow label="LLM Reviewed" value={summary.llm_reviewed} />
        <MetricRow label="Qualified" value={summary.qualified} highlight />
        <MetricRow label="Submitted" value={summary.submitted} highlight />
      </div>
    </Panel>
  );
}

function ErrorsPanel({ errors }: { errors: any[] }) {
  if (!errors || errors.length === 0) return null;
  
  return (
    <Panel title="Critical Errors" icon={XCircle} className="col-span-2 border-red-500/20 bg-red-500/5">
      <div className="space-y-3">
        {errors.slice(-3).map((event: any, i: number) => {
          const time = event.timestamp.split('T')[1].substring(0, 8);
          return (
            <div key={i} className="flex gap-3 text-sm text-red-400 font-medium bg-red-500/10 p-3 rounded-lg border border-red-500/20">
              <span className="font-mono shrink-0 opacity-50">[{time}]</span>
              <span>{event.message}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// --- Loading skeleton ---

function OverviewSkeleton() {
  return (
    <div className="p-8 space-y-6 animate-pulse bg-black min-h-screen">
      <div className="h-8 w-48 bg-white/[0.05] rounded" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-[200px] bg-white/[0.03] rounded-xl border border-white/[0.05]" />
        <div className="h-[200px] bg-white/[0.03] rounded-xl border border-white/[0.05]" />
        <div className="h-[280px] bg-white/[0.03] rounded-xl border border-white/[0.05]" />
        <div className="h-[280px] bg-white/[0.03] rounded-xl border border-white/[0.05]" />
      </div>
    </div>
  );
}

// --- Page ---

export default function Dashboard() {
  const { data: viewmodel, isLoading } = useViewModel();

  if (isLoading) return <OverviewSkeleton />;

  if (!viewmodel) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen text-white/40 bg-black">
        Failed to load RunViewModel. Is the pipeline running?
      </div>
    );
  }

  const {
    version,
    header,
    health,
    progress,
    inference,
    efficiency,
    decision_summary,
    timeline,
    notifications,
    errors
  } = viewmodel;

  return (
    <div className="min-h-screen flex flex-col bg-[#000000] text-white selection:bg-white/20 overflow-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between px-8 py-6 border-b border-white/[0.08] shrink-0 bg-black/80 backdrop-blur-xl sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-white to-white/60 flex items-center justify-center">
            <LayoutDashboard className="w-4 h-4 text-black" />
          </div>
          <div>
            <h1 className="text-[15px] font-semibold tracking-tight text-white/90">Operations Command Center</h1>
            <p className="text-[13px] text-white/40 mt-0.5">Unified Runtime State View</p>
          </div>
        </div>
      </div>

      <div className="flex-1 p-8 max-w-[1400px] w-full mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Row 1 */}
          <HeaderPanel header={header} version={version} />
          <HealthPanel health={health} />
          
          {/* Row 2 */}
          <PipelinePanel progress={progress} />
          <InferencePanel inference={inference} />
          
          {/* Row 3 */}
          <TimelinePanel timeline={timeline} />
          <EfficiencyPanel efficiency={efficiency} />
          
          {/* Row 4 */}
          <DecisionSummaryPanel summary={decision_summary} />
          <NotificationsPanel notifications={notifications} />
          
          {/* Errors Row (only shows if errors exist) */}
          <ErrorsPanel errors={errors} />
          
        </div>
      </div>
    </div>
  );
}
