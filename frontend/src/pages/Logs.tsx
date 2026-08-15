import { useState } from 'react';
import {
  useLogsPipeline,
  useLogsRuntime,
  useLogsEventbus,
  useLogsErrors,
  useLogsWarnings,
  useLogsLedger,
} from '@/lib/hooks';
import { PageHeader } from '@/components/operations/PageHeader';

type LogTab = 'pipeline' | 'runtime' | 'eventbus' | 'errors' | 'warnings' | 'ledger';

export default function Logs() {
  const [activeTab, setActiveTab] = useState<LogTab>('pipeline');

  const { data: pipeline, isLoading: pipelineLoading } = useLogsPipeline();
  const { data: runtime, isLoading: runtimeLoading } = useLogsRuntime();
  const { data: eventbus, isLoading: eventbusLoading } = useLogsEventbus();
  const { data: errors, isLoading: errorsLoading } = useLogsErrors();
  const { data: warnings, isLoading: warningsLoading } = useLogsWarnings();
  const { data: ledger, isLoading: ledgerLoading } = useLogsLedger();

  const tabs: Array<{ id: LogTab; label: string; data: any; loading: boolean }> = [
    { id: 'pipeline', label: 'Pipeline', data: pipeline, loading: pipelineLoading },
    { id: 'runtime', label: 'Runtime', data: runtime, loading: runtimeLoading },
    { id: 'eventbus', label: 'EventBus', data: eventbus, loading: eventbusLoading },
    { id: 'ledger', label: 'Ledger', data: ledger, loading: ledgerLoading },
    { id: 'warnings', label: 'Warnings', data: warnings, loading: warningsLoading },
    { id: 'errors', label: 'Errors', data: errors, loading: errorsLoading },
  ];

  const activeTabData = tabs.find(t => t.id === activeTab);
  const logLines = (activeTabData?.data?.logs || activeTabData?.data || []) as string[];

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <PageHeader
        coordinate="06 · 02"
        title="Logs"
        subtitle="Read-only stream of operational logs across all services."
      />

      <div role="tablist" aria-label="Log sources" className="flex items-center border-b border-border px-4 bg-background/80 shrink-0">
        {tabs.map(tab => (
          <button
            key={tab.id}
            role="tab"
            id={`log-tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`log-panel-${tab.id}`}
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
            {tab.id === 'errors' && tab.data?.logs?.length > 0 && (
              <span className="w-2 h-2 rounded-full bg-failed"></span>
            )}
            {tab.id === 'warnings' && tab.data?.logs?.length > 0 && (
              <span className="w-2 h-2 rounded-full bg-degraded"></span>
            )}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`log-panel-${activeTab}`} className="flex-1 bg-console overflow-auto p-4 flex flex-col-reverse">
        {activeTabData?.loading ? (
          <div className="text-muted-foreground font-mono text-xs animate-pulse">Loading logs...</div>
        ) : logLines.length > 0 ? (
          <div className="font-mono text-[11px] leading-[1.6] space-y-1">
            {logLines.map((line, idx) => {
              // Basic colorization based on log levels if they exist in the string
              let colorClass = "text-gray-300";
              if (line.includes('ERROR') || line.includes('CRITICAL')) colorClass = "text-failed";
              else if (line.includes('WARN')) colorClass = "text-degraded";
              else if (line.includes('INFO')) colorClass = "text-running";
              else if (line.includes('DEBUG')) colorClass = "text-gray-500";
              
              return (
                <div key={idx} className={`whitespace-pre-wrap break-all ${colorClass}`}>
                  {line}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-muted-foreground font-mono text-xs opacity-50 flex items-center justify-center h-full">
            No logs available in this stream.
          </div>
        )}
      </div>
    </div>
  );
}
