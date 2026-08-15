import { useDeveloper } from '@/lib/hooks';
import { Activity, Cpu, Network, Package } from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { ErrorState } from '@/components/operations/ErrorState';

export default function Developer() {
  const { data: devData, isLoading, isError, refetch } = useDeveloper();

  if (isError) {
    return (
      <div className="h-full flex items-center justify-center bg-background p-6">
        <div className="w-full max-w-2xl"><ErrorState message="Developer diagnostics could not be loaded." onRetry={() => refetch()} /></div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-background p-6">
        <div className="w-full max-w-2xl"><GridSkeleton rows={4} /></div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <PageHeader
        coordinate="06 · 03"
        title="Developer Console"
        subtitle="Internal administrative diagnostics and API health."
        actions={<StatusBadge status={devData?.api_health === 'Healthy' ? 'HEALTHY' : 'DEGRADED'} />}
      />

      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          
          {/* Environment */}
          <div className="bg-surface border border-border/50 rounded-md p-5">
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
          <div className="bg-surface border border-border/50 rounded-md p-5">
            <h2 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <Activity className="w-4 h-4 text-muted-foreground" /> Feature Flags
            </h2>
            <div className="space-y-3">
              {Object.entries(devData?.feature_flags || {}).map(([key, enabled]) => (
                <div key={key} className="flex justify-between items-center text-xs">
                  <span className="text-muted-foreground">{key}</span>
                  {enabled ? (
                    <span className="text-healthy font-bold text-[10px] bg-healthy/10 px-1.5 py-0.5 rounded">ON</span>
                  ) : (
                    <span className="text-muted-foreground font-bold text-[10px] bg-muted px-1.5 py-0.5 rounded">OFF</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Thread Pools & Runtime */}
          <div className="bg-surface border border-border/50 rounded-md p-5">
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
          <div className="bg-surface border border-border/50 rounded-md p-5 lg:col-span-3">
            <h2 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <Network className="w-4 h-4 text-muted-foreground" /> Registered API Routes
            </h2>
            <div className="max-h-[300px] overflow-auto border border-border/40 rounded-md bg-background">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-muted/30 border-b border-border">
                  <tr>
                    <th className="px-3 py-2 font-mono text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Method</th>
                    <th className="px-3 py-2 font-mono text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Path</th>
                    <th className="px-3 py-2 font-mono text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Name</th>
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
