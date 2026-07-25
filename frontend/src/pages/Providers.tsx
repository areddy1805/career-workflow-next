import { useProviders } from '@/lib/hooks';
import { Server, CheckCircle2, XCircle, Clock, Activity } from 'lucide-react';
import { StatusBadge } from '@/components/operations/StatusBadge';
import { SectionTitle } from '@/components/operations/SectionTitle';
import { cn } from '@/lib/utils';
import { RelativeTime } from '@/components/RelativeTime';
import { StatRow } from '@/components/operations/StatRow';

const PROVIDER_ICONS: Record<string, string> = {
  naukri: 'N',
  google: 'G',
  indeed: 'I',
  linkedin: 'in',
};

const PROVIDER_COLORS: Record<string, string> = {
  naukri: 'text-indigo-500 bg-indigo-500/10 border-indigo-500/20',
  google: 'text-blue-500 bg-blue-500/10 border-blue-500/20',
  indeed: 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20',
  linkedin: 'text-sky-500 bg-sky-500/10 border-sky-500/20',
};

export default function Providers() {
  const { data, isLoading } = useProviders();

  const providers = Object.entries(data?.providers || {}).map(([id, p]: [string, any]) => ({
    id,
    name: id.charAt(0).toUpperCase() + id.slice(1),
    healthy: p.status === 'active' || p.status === 'HEALTHY',
    enabled: p.status !== 'inactive',
    native_apply: p.native_apply,
    ats_integration: p.ats !== 'Various',
    rate_limit_remaining: p.rate_limit_remaining || '—',
    rate_limit_total: p.rate_limit_total || '—',
    latency_ms: p.average_latency_seconds ? Math.round(p.average_latency_seconds * 1000) : 0,
    last_run: p.last_run
  }));

  return (
    <div className="h-full flex flex-col animate-in fade-in duration-300">
      <SectionTitle 
        title="Providers" 
        subtitle="Health, capabilities, and telemetry for integrated job boards."
        action={
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-muted-foreground uppercase tracking-widest font-semibold flex items-center gap-1.5"><Server className="w-3.5 h-3.5" /> Total Integrations</span>
            <span className="bg-primary/20 text-primary border border-primary/20 px-2 py-0.5 rounded text-[11px] font-bold font-mono">{providers.length}</span>
          </div>
        }
      />

      <div className="flex-1 overflow-auto pb-8">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="bg-muted/50 rounded-md h-[280px] animate-pulse"></div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {providers?.map((provider: any) => (
              <div key={provider.id} className="bg-card border border-border rounded-md shadow-card flex flex-col hover:border-foreground/20 transition-colors group">
                {/* Header */}
                <div className="p-5 border-b border-border bg-card/50 flex justify-between items-start">
                  <div className="flex items-center gap-3">
                    <div className={cn('w-10 h-10 rounded border flex items-center justify-center text-sm font-bold tracking-wider', PROVIDER_COLORS[provider.id] || 'bg-muted/30 border-border text-foreground')}>
                      {PROVIDER_ICONS[provider.id] || provider.id[0].toUpperCase()}
                    </div>
                    <div>
                      <h3 className="font-semibold text-sm tracking-tight text-foreground">{provider.name}</h3>
                      <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-widest mt-0.5">{provider.id}</p>
                    </div>
                  </div>
                </div>

                {/* Body */}
                <div className="p-5 flex-1 flex flex-col justify-between space-y-4">
                  <div className="space-y-0">
                    <StatRow 
                      label="Status"
                      value={
                        <StatusBadge 
                          status={provider.healthy ? 'success' : 'error'} 
                          label={provider.healthy ? 'HEALTHY' : 'UNHEALTHY'} 
                          pulse={provider.healthy}
                        />
                      }
                      className="py-2"
                    />
                    <StatRow 
                      label="Integration"
                      value={
                        provider.enabled ? (
                          <span className="flex items-center gap-1.5 text-emerald-500 font-semibold tracking-tight"><CheckCircle2 className="w-3.5 h-3.5" /> Enabled</span>
                        ) : (
                          <span className="flex items-center gap-1.5 text-muted-foreground font-medium tracking-tight"><XCircle className="w-3.5 h-3.5" /> Disabled</span>
                        )
                      }
                      className="py-2"
                    />
                    <StatRow 
                      label="Capabilities"
                      value={
                        <div className="flex gap-2">
                          {provider.native_apply && <span className="px-1.5 py-0.5 bg-primary/10 border border-primary/20 text-primary rounded text-[9px] font-bold tracking-widest uppercase">Native</span>}
                          {provider.ats_integration && <span className="px-1.5 py-0.5 bg-blue-500/10 border border-blue-500/20 text-blue-500 rounded text-[9px] font-bold tracking-widest uppercase">ATS</span>}
                          {!provider.native_apply && !provider.ats_integration && <span className="text-muted-foreground">Standard</span>}
                        </div>
                      }
                      className="py-2"
                    />
                    <StatRow 
                      label="Rate Limits"
                      value={<span className="font-mono bg-muted/40 px-1.5 py-0.5 rounded text-muted-foreground group-hover:text-foreground transition-colors">{provider.rate_limit_remaining} / {provider.rate_limit_total}</span>}
                      className="py-2 border-0"
                    />
                  </div>

                  {/* Footer Metrics */}
                  <div className="grid grid-cols-2 gap-px bg-border pt-4 mt-2">
                    <div className="bg-card px-2 py-3 flex flex-col items-center justify-center text-center">
                      <Clock className="w-3.5 h-3.5 text-muted-foreground mb-1.5" />
                      <p className="text-[13px] font-bold font-mono text-foreground">{provider.latency_ms}ms</p>
                      <p className="text-[9px] text-muted-foreground uppercase tracking-widest font-semibold mt-0.5">Latency</p>
                    </div>
                    <div className="bg-card px-2 py-3 flex flex-col items-center justify-center text-center">
                      <Activity className="w-3.5 h-3.5 text-muted-foreground mb-1.5" />
                      <p className="text-[13px] font-bold font-mono text-foreground">
                        {provider.last_run ? <RelativeTime date={provider.last_run} /> : 'Never'}
                      </p>
                      <p className="text-[9px] text-muted-foreground uppercase tracking-widest font-semibold mt-0.5">Last Sync</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
