import { useState } from 'react';
import { useAuditPipeline, useAuditFilters, useAuditRanking, useAuditSystem } from '@/lib/hooks';
import { FileJson } from 'lucide-react';
import { PageHeader } from '@/components/operations/PageHeader';
import { GridSkeleton } from '@/components/operations/GridSkeleton';

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
      <PageHeader
        coordinate="06 · 04"
        title="Audit"
        subtitle="Read-only operational view of system configurations, ranking logic, and pipeline rules."
      />

      <div role="tablist" aria-label="Audit surfaces" className="flex items-center border-b border-border px-4 bg-background/80 shrink-0">
        {tabs.map(tab => (
          <button
            key={tab.id}
            role="tab"
            id={`audit-tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`audit-panel-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            onKeyDown={e => {
              const ids = tabs.map(t => t.id);
              const idx = ids.indexOf(activeTab);
              if (e.key === 'ArrowRight') { e.preventDefault(); setActiveTab(ids[(idx + 1) % ids.length]); }
              else if (e.key === 'ArrowLeft') { e.preventDefault(); setActiveTab(ids[(idx - 1 + ids.length) % ids.length]); }
            }}
            className={`flex items-center gap-2 px-0 py-3 mr-6 text-xs font-medium border-b-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset ${
              activeTab === tab.id
                ? 'border-foreground text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border/50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`audit-panel-${activeTab}`} className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl mx-auto space-y-4">
          <div className="flex items-center gap-2 mb-2 text-muted-foreground">
            <FileJson className="w-4 h-4" />
            <span className="text-xs font-semibold uppercase tracking-wider">
              {activeTabData?.label} Configuration
            </span>
          </div>
          
          <div className="bg-surface border border-border/50 rounded-lg p-4 overflow-auto">
            {activeTabData?.loading ? (
              <GridSkeleton rows={3} />
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
