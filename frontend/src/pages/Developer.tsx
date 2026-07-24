import { useDeveloper } from '@/lib/hooks';
import { Zap, Activity, Cpu, Network, Package } from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';

export default function Developer() {
  const { data: devData, isLoading } = useDeveloper();

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-background">
        <div className="animate-pulse text-muted-foreground text-sm font-mono flex items-center gap-2">
          <Zap className="w-4 h-4 text-primary" /> Booting Developer Console...
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" /> Developer Console
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Internal administrative diagnostics and API health.
          </p>
        </div>
        <StatusBadge status={devData?.api_health === 'Healthy' ? 'HEALTHY' : 'DEGRADED'} />
      </div>

      <div className="flex-1 overflow-auto bg-muted/5 p-6">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          
          {/* Environment */}
          <div className="bg-card border border-border/50 rounded-lg p-5">
            <h2 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <Package className="w-4 h-4 text-muted-foreground" /> Environment
            </h2>
            <div className="space-y-3">
              {Object.entries(devData?.runtime_environment || {}).map(([key, val]) => (
                <div key={key} className="flex justify-between text-xs">
                  <span className="text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="font-mono text-foreground font-medium">{String(val)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Feature Flags */}
          <div className="bg-card border border-border/50 rounded-lg p-5">
            <h2 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <Activity className="w-4 h-4 text-muted-foreground" /> Feature Flags
            </h2>
            <div className="space-y-3">
              {Object.entries(devData?.feature_flags || {}).map(([key, enabled]) => (
                <div key={key} className="flex justify-between items-center text-xs">
                  <span className="text-muted-foreground">{key}</span>
                  {enabled ? (
                    <span className="text-emerald-500 font-bold text-[10px] bg-emerald-500/10 px-1.5 py-0.5 rounded">ON</span>
                  ) : (
                    <span className="text-muted-foreground font-bold text-[10px] bg-muted px-1.5 py-0.5 rounded">OFF</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Thread Pools & Runtime */}
          <div className="bg-card border border-border/50 rounded-lg p-5">
            <h2 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <Cpu className="w-4 h-4 text-muted-foreground" /> Runtime Diagnostics
            </h2>
            <div className="space-y-3">
              {Object.entries(devData?.diagnostics || {}).map(([key, val]) => (
                <div key={key} className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{key}</span>
                  <span className="font-mono text-foreground">{String(val)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Registered Routes */}
          <div className="bg-card border border-border/50 rounded-lg p-5 lg:col-span-3">
            <h2 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <Network className="w-4 h-4 text-muted-foreground" /> Registered API Routes
            </h2>
            <div className="max-h-[300px] overflow-auto border border-border/40 rounded-md bg-background">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-muted/80 backdrop-blur border-b border-border/40">
                  <tr>
                    <th className="px-3 py-2 font-medium text-muted-foreground w-20">Method</th>
                    <th className="px-3 py-2 font-medium text-muted-foreground">Path</th>
                    <th className="px-3 py-2 font-medium text-muted-foreground">Name</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {devData?.routes?.map((route: string, idx: number) => (
                    <tr key={idx} className="hover:bg-muted/30 transition-colors">
                      <td className="px-3 py-1.5 font-mono text-[10px] font-bold text-primary">GET</td>
                      <td className="px-3 py-1.5 font-mono text-muted-foreground">{route}</td>
                      <td className="px-3 py-1.5">—</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
