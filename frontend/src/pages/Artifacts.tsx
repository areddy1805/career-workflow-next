import { useQuery } from '@tanstack/react-query';
import { fetchArtifacts, fetchRunArtifacts, fetchRunArtifactContent } from '@/lib/api';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useState } from 'react';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { usePreferences } from '@/store/preferences';
import JsonView from 'react18-json-view';
import 'react18-json-view/src/style.css';
import { Database, FileJson, FileText, ChevronRight } from 'lucide-react';
import { CopyButton } from '@/components/CopyButton';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileIcon({ name }: { name: string }) {
  if (name.endsWith('.json')) return <FileJson className="w-3.5 h-3.5 text-blue-400 shrink-0" />;
  return <FileText className="w-3.5 h-3.5 text-muted-foreground/60 shrink-0" />;
}

export default function Artifacts() {
  const { data: artifacts = [], isLoading } = useQuery({
    queryKey: ['artifacts'],
    queryFn: fetchArtifacts,
  });

  const { theme } = usePreferences();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  // Load file list for selected run
  const { data: runDetail, isLoading: runDetailLoading } = useQuery({
    queryKey: ['run-artifacts', selectedRunId],
    queryFn: () => fetchRunArtifacts(selectedRunId!),
    enabled: !!selectedRunId,
  });

  // Load content for selected file
  const { data: fileContent, isLoading: fileLoading } = useQuery({
    queryKey: ['run-artifact-content', selectedRunId, selectedFile],
    queryFn: () => fetchRunArtifactContent(selectedRunId!, selectedFile!),
    enabled: !!selectedRunId && !!selectedFile,
  });

  const fileList: Array<{ name: string; size_bytes: number; suffix: string }> = runDetail?.files || [];

  const handleRunSelect = (runId: string) => {
    setSelectedRunId(runId);
    setSelectedFile(null);
  };

  const selectedArtifact = artifacts.find((a: any) => a.run_id === selectedRunId);

  return (
    <div className="h-full flex flex-col bg-background">
      <div className="flex items-center px-4 py-2 border-b shrink-0 bg-background/95 backdrop-blur z-10">
        <h2 className="font-semibold tracking-tight">Artifact Explorer</h2>
      </div>

      <div className="flex-1 overflow-hidden">
        <ResizablePanelGroup direction="horizontal">
          {/* Left: Run List */}
          <ResizablePanel defaultSize={20} minSize={15} maxSize={30} className="bg-card flex flex-col">
            <div className="h-10 border-b flex items-center px-4 bg-secondary/30 shrink-0">
              <Database className="w-3.5 h-3.5 text-muted-foreground mr-2" />
              <span className="font-semibold text-xs text-muted-foreground uppercase tracking-wider">Runs ({artifacts.length})</span>
            </div>
            <ScrollArea className="flex-1 custom-scrollbar">
              {isLoading ? (
                <div className="p-2 space-y-1">
                  {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-8 bg-muted animate-pulse rounded" />)}
                </div>
              ) : (
                <div className="flex flex-col">
                  {artifacts.map((a: any) => {
                    const status = a.result?.status || a.state?.status || 'UNKNOWN';
                    const statusColor = status === 'SUCCESS' ? 'text-green-500' : status === 'FAILED' ? 'text-red-500' : 'text-muted-foreground';
                    return (
                      <button
                        key={a.run_id}
                        onClick={() => handleRunSelect(a.run_id)}
                        className={cn(
                          'flex items-center gap-2 px-3 py-2 text-xs font-mono border-b border-border/40 transition-colors text-left',
                          selectedRunId === a.run_id
                            ? 'bg-primary/10 text-primary border-l-2 border-l-primary'
                            : 'hover:bg-muted/50 border-l-2 border-l-transparent'
                        )}
                      >
                        <ChevronRight className={cn('w-3 h-3 shrink-0 transition-transform', selectedRunId === a.run_id && 'rotate-90')} />
                        <div className="flex-1 min-w-0">
                          <div className="truncate">{a.run_id.replace('Z', '').slice(-12)}</div>
                          <div className={cn('text-[9px] uppercase font-semibold tracking-wide', statusColor)}>{status}</div>
                        </div>
                      </button>
                    );
                  })}
                  {!artifacts.length && <div className="p-4 text-xs text-muted-foreground text-center">No artifacts found.</div>}
                </div>
              )}
            </ScrollArea>
          </ResizablePanel>

          <ResizableHandle withHandle className="bg-border/50 hover:bg-primary/50 transition-colors w-1" />

          {/* Middle: File List */}
          <ResizablePanel defaultSize={20} minSize={15} maxSize={35} className="bg-card flex flex-col border-r border-border/50">
            <div className="h-10 border-b flex items-center px-4 bg-secondary/30 shrink-0">
              <FileJson className="w-3.5 h-3.5 text-muted-foreground mr-2" />
              <span className="font-semibold text-xs text-muted-foreground uppercase tracking-wider">
                Files {fileList.length ? `(${fileList.length})` : ''}
              </span>
            </div>
            <ScrollArea className="flex-1">
              {!selectedRunId ? (
                <div className="p-4 text-xs text-muted-foreground text-center">Select a run to browse files.</div>
              ) : runDetailLoading ? (
                <div className="p-2 space-y-1">
                  {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-8 bg-muted animate-pulse rounded" />)}
                </div>
              ) : (
                <div className="flex flex-col">
                  {fileList.map((file) => (
                    <button
                      key={file.name}
                      onClick={() => setSelectedFile(file.name)}
                      className={cn(
                        'flex items-center gap-2 px-3 py-2 text-xs border-b border-border/40 transition-colors text-left',
                        selectedFile === file.name
                          ? 'bg-primary/10 text-primary border-l-2 border-l-primary'
                          : 'hover:bg-muted/50 border-l-2 border-l-transparent'
                      )}
                    >
                      <FileIcon name={file.name} />
                      <div className="flex-1 min-w-0">
                        <div className="truncate font-mono text-[11px]">{file.name}</div>
                        <div className="text-[9px] text-muted-foreground">{formatBytes(file.size_bytes)}</div>
                      </div>
                    </button>
                  ))}
                  {!fileList.length && selectedRunId && (
                    <div className="p-4 text-xs text-muted-foreground text-center">No files found.</div>
                  )}
                </div>
              )}
            </ScrollArea>
          </ResizablePanel>

          <ResizableHandle withHandle className="bg-border/50 hover:bg-primary/50 transition-colors w-1" />

          {/* Right: File Content */}
          <ResizablePanel defaultSize={60} className="bg-card flex flex-col relative z-20">
            {selectedFile && selectedRunId ? (
              <>
                <div className="px-3 border-b h-10 flex items-center justify-between bg-secondary/10 shrink-0">
                  <div className="flex items-center gap-2">
                    <FileIcon name={selectedFile} />
                    <span className="text-xs font-mono font-medium">{selectedFile}</span>
                    {selectedArtifact && (
                      <Badge variant="outline" className="text-[9px] font-mono ml-1">
                        {selectedRunId?.slice(-8)}
                      </Badge>
                    )}
                  </div>
                  <CopyButton value={JSON.stringify(fileContent, null, 2)} className="h-7 w-7" />
                </div>
                <div className="flex-1 overflow-auto bg-background/50">
                  {fileLoading ? (
                    <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                      Loading…
                    </div>
                  ) : typeof fileContent === 'object' && fileContent !== null ? (
                    <ScrollArea className="h-full w-full">
                      <div className="p-4">
                        <JsonView
                          src={fileContent}
                          dark={theme === 'dark'}
                          theme="vscode"
                          enableClipboard={true}
                          collapsed={2}
                          style={{ backgroundColor: 'transparent', fontSize: '12px', fontFamily: 'var(--font-mono, monospace)' }}
                        />
                      </div>
                    </ScrollArea>
                  ) : (
                    <ScrollArea className="h-full w-full">
                      <pre className="p-4 text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                        {String(fileContent?.content || fileContent || '')}
                      </pre>
                    </ScrollArea>
                  )}
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground space-y-4 bg-muted/10">
                <FileJson className="w-12 h-12 text-muted/30" />
                <p className="text-sm">{selectedRunId ? 'Select a file to inspect its contents.' : 'Select a run from the sidebar to explore its artifacts.'}</p>
              </div>
            )}
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
    </div>
  );
}
