import { useState } from 'react';
import {
  useLogsPipeline,
  useLogsRuntime,
  useLogsEventbus,
  useLogsErrors,
  useLogsWarnings,
  useLogsLedger,
} from '@/lib/hooks';
import { Terminal } from 'lucide-react';

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
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <Terminal className="w-4 h-4 text-primary" /> System Logs
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Read-only stream of operational logs across all services.
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
            {tab.id === 'errors' && tab.data?.logs?.length > 0 && (
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
            )}
            {tab.id === 'warnings' && tab.data?.logs?.length > 0 && (
              <span className="w-2 h-2 rounded-full bg-amber-500"></span>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 bg-[#0d1117] overflow-auto p-4 flex flex-col-reverse">
        {activeTabData?.loading ? (
          <div className="text-muted-foreground font-mono text-xs animate-pulse">Loading logs...</div>
        ) : logLines.length > 0 ? (
          <div className="font-mono text-[11px] leading-[1.6] space-y-1">
            {logLines.map((line, idx) => {
              // Basic colorization based on log levels if they exist in the string
              let colorClass = "text-gray-300";
              if (line.includes('ERROR') || line.includes('CRITICAL')) colorClass = "text-red-400";
              else if (line.includes('WARN')) colorClass = "text-amber-400";
              else if (line.includes('INFO')) colorClass = "text-blue-300";
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
