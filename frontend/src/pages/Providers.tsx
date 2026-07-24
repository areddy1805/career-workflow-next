import { useProviders } from '@/lib/hooks';
import { Server, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';

export default function Providers() {
  const { data, isLoading } = useProviders();

  const providers = Object.entries(data?.providers || {}).map(([id, p]: [string, any]) => ({
    id,
    name: id.charAt(0).toUpperCase() + id.slice(1),
    healthy: p.status === 'active',
    enabled: p.status !== 'inactive',
    native_apply: p.native_apply,
    ats_integration: p.ats !== 'Various',
    rate_limit_remaining: p.rate_limit_remaining || '—',
    rate_limit_total: p.rate_limit_total || '—',
    latency_ms: p.average_latency_seconds ? Math.round(p.average_latency_seconds * 1000) : 0,
    last_run: p.last_run
  }));

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <Server className="w-4 h-4 text-primary" /> Providers
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Health and capabilities of integrated job boards.
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-muted/5 p-6">
        <div className="max-w-5xl mx-auto">
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="bg-card border border-border/50 rounded-lg p-5 h-40 animate-pulse"></div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {providers?.map((provider: any) => (
                <div key={provider.name} className="bg-card border border-border/50 rounded-lg overflow-hidden flex flex-col">
                  <div className="p-4 border-b border-border/40 flex justify-between items-start bg-secondary/10">
                    <div>
                      <h3 className="font-semibold text-base">{provider.name}</h3>
                      <p className="text-[10px] text-muted-foreground font-mono mt-0.5">{provider.id}</p>
                    </div>
                    <StatusBadge status={provider.healthy ? 'HEALTHY' : 'UNHEALTHY'} />
                  </div>
                  <div className="p-4 flex-1 flex flex-col justify-between">
                    <div className="space-y-3">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">Status</span>
                        {provider.enabled ? (
                          <span className="flex items-center gap-1 text-emerald-500 font-medium"><CheckCircle2 className="w-3 h-3" /> Enabled</span>
                        ) : (
                          <span className="flex items-center gap-1 text-muted-foreground font-medium"><XCircle className="w-3 h-3" /> Disabled</span>
                        )}
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">Capabilities</span>
                        <div className="flex gap-2">
                          {provider.native_apply && <span className="px-1.5 py-0.5 bg-primary/10 text-primary rounded text-[9px] font-bold">NATIVE</span>}
                          {provider.ats_integration && <span className="px-1.5 py-0.5 bg-blue-500/10 text-blue-500 rounded text-[9px] font-bold">ATS</span>}
                        </div>
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">Rate Limits</span>
                        <span className="font-mono">{provider.rate_limit_remaining ?? 0} / {provider.rate_limit_total ?? 0}</span>
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">Latency</span>
                        <span className="font-mono flex items-center gap-1">
                          <Clock className="w-3 h-3 text-muted-foreground" />
                          {provider.latency_ms ?? 0}ms
                        </span>
                      </div>
                    </div>
                    {provider.last_run && (
                      <div className="mt-4 pt-3 border-t border-border/40 text-[10px] text-muted-foreground text-center">
                        Last synced: {new Date(provider.last_run).toLocaleString()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
