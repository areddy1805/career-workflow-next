import { useState } from 'react';
import { useAuditPipeline, useAuditFilters, useAuditRanking, useAuditSystem } from '@/lib/hooks';
import { ShieldAlert, FileJson } from 'lucide-react';

type AuditTab = 'pipeline' | 'filters' | 'ranking' | 'system';

export default function Audit() {
  const [activeTab, setActiveTab] = useState<AuditTab>('pipeline');

  const { data: pipelineData, isLoading: pipelineLoading } = useAuditPipeline();
  const { data: filtersData, isLoading: filtersLoading } = useAuditFilters();
  const { data: rankingData, isLoading: rankingLoading } = useAuditRanking();
  const { data: systemData, isLoading: systemLoading } = useAuditSystem();

  const tabs: Array<{ id: AuditTab; label: string; data: any; loading: boolean }> = [
    { id: 'pipeline', label: 'Pipeline', data: pipelineData, loading: pipelineLoading },
    { id: 'filters', label: 'Filters', data: filtersData, loading: filtersLoading },
    { id: 'ranking', label: 'Ranking', data: rankingData, loading: rankingLoading },
    { id: 'system', label: 'System State', data: systemData, loading: systemLoading },
  ];

  const activeTabData = tabs.find(t => t.id === activeTab);

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-primary" /> System Audit
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Read-only operational view of system configurations, ranking logic, and pipeline rules.
          </p>
        </div>
      </div>

      <div className="flex items-center border-b border-border/40 px-6 bg-background/80">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-0 py-3 mr-6 text-xs font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border/50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto bg-muted/5 p-6">
        <div className="max-w-4xl mx-auto space-y-4">
          <div className="flex items-center gap-2 mb-2 text-muted-foreground">
            <FileJson className="w-4 h-4" />
            <span className="text-xs font-semibold uppercase tracking-wider">
              {activeTabData?.label} Configuration
            </span>
          </div>
          
          <div className="bg-card border border-border/50 rounded-lg p-4 overflow-auto shadow-sm">
            {activeTabData?.loading ? (
              <div className="animate-pulse space-y-2">
                <div className="h-4 bg-muted w-1/4 rounded"></div>
                <div className="h-4 bg-muted w-1/2 rounded"></div>
                <div className="h-4 bg-muted w-1/3 rounded"></div>
              </div>
            ) : (
              <pre className="text-[11px] font-mono leading-relaxed text-foreground/90">
                {JSON.stringify(activeTabData?.data, null, 2) || 'No data available'}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
