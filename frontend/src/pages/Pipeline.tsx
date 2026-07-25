import { useState, useEffect, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { launchPipeline } from '@/lib/api';
import { usePipelineState } from '@/lib/hooks';
import { Play, AlertTriangle, ArrowDown, Terminal } from 'lucide-react';
import { cn } from '@/lib/utils';
import { RelativeTime } from '@/components/RelativeTime';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { StatusBadge } from '@/components/operations/StatusBadge';
import { SectionTitle } from '@/components/operations/SectionTitle';

export default function Pipeline() {
  const queryClient = useQueryClient();
  const [live, setLive]                       = useState(false);
  const [maxApplications, setMaxApplications] = useState(500);
  const [canary, setCanary]                   = useState(false);
  const [forceLive, setForceLive]             = useState(false);
  const [confirmOpen, setConfirmOpen]         = useState(false);
  const [autoScroll, setAutoScroll]           = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error } = usePipelineState();

  const launchMutation = useMutation({
    mutationFn: launchPipeline,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline_state'] }),
  });

  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [data?.log, autoScroll]);

  const handleLogScroll = () => {
    const el = logContainerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  };

  const handleLaunchClick = () => {
    if (live) {
      setConfirmOpen(true);
    } else {
      launchMutation.mutate({ live, max_applications: maxApplications, canary, force_live: forceLive });
    }
  };

  const handleConfirmedLaunch = () => {
    launchMutation.mutate({ live, max_applications: maxApplications, canary, force_live: forceLive });
  };

  const isRunning = data?.running ?? false;
  const state     = data?.state   ?? {};

  if (isLoading && !data) {
    return (
      <div className="p-6 text-sm text-muted-foreground animate-pulse">
        Initializing Pipeline Control…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-sm text-red-500 font-medium">
        Failed to load pipeline state: {(error as Error).message}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col animate-in fade-in duration-300">
      <SectionTitle 
        title="Pipeline Control" 
        subtitle="Configure, execute, and observe the application engine."
        action={
          <StatusBadge 
            status={isRunning ? 'success' : 'neutral'} 
            label={isRunning ? 'RUNNING' : 'IDLE'} 
            pulse={isRunning} 
          />
        }
      />

      <div className="flex flex-col lg:flex-row gap-6 pb-6">
        {/* Left: Log viewer */}
        <div className="flex-[1.8] flex flex-col gap-0 min-w-0 border border-border bg-[#0a0a0a] rounded-md shadow-card overflow-hidden">
          <div className="px-4 py-3 border-b border-border bg-card/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="w-3.5 h-3.5 text-muted-foreground" />
              <h2 className="text-[11px] font-semibold tracking-widest uppercase text-muted-foreground">Live Output</h2>
            </div>
            {!autoScroll && (
              <button
                className="text-[10px] font-medium tracking-tight text-foreground hover:text-foreground/70 transition-colors flex items-center gap-1.5"
                onClick={() => {
                  setAutoScroll(true);
                  logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                }}
              >
                <ArrowDown className="w-3 h-3" /> Scroll to bottom
              </button>
            )}
          </div>
          <div
            ref={logContainerRef}
            onScroll={handleLogScroll}
            className="h-[520px] overflow-y-auto p-4 relative"
          >
            <pre className="text-[11px] font-mono text-zinc-400 leading-relaxed whitespace-pre-wrap">
              {data?.log ?? 'No output yet. Launch the pipeline to begin.'}
            </pre>
            <div ref={logEndRef} />
          </div>
        </div>

        {/* Right: Telemetry + Config */}
        <div className="flex-1 flex flex-col gap-6 min-w-[300px]">

          {/* Telemetry */}
          <div className="border border-border bg-card rounded-md shadow-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-card/50">
              <h2 className="text-[11px] font-semibold tracking-widest uppercase text-muted-foreground">Telemetry</h2>
            </div>
            <div className="grid grid-cols-2 gap-px bg-border/50">
              {[
                { label: 'Status',  value: isRunning ? 'Running' : 'Idle' },
                { label: 'PID',     value: state.pid ?? '—' },
                { label: 'Mode',    value: state.live ? 'Live' : 'Dry Run' },
                { label: 'Started', value: state.started_at
                    ? <RelativeTime date={state.started_at} />
                    : '—' },
              ].map(item => (
                <div key={item.label} className="bg-card px-4 py-3 flex flex-col gap-1.5">
                  <span className="text-[9px] uppercase font-semibold text-muted-foreground tracking-widest">{item.label}</span>
                  <span className="text-sm font-medium tracking-tight text-foreground">{item.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Run Configuration */}
          <div className="border border-border bg-card rounded-md shadow-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-card/50">
              <h2 className="text-[11px] font-semibold tracking-widest uppercase text-muted-foreground">Configuration</h2>
            </div>
            <div className="p-5 space-y-5">

              {/* Mode toggle */}
              <div className="flex gap-1 p-1 bg-muted/40 rounded-md w-full border border-border">
                <button
                  className={cn(
                    'flex-1 text-[11px] py-1.5 rounded-sm transition-all duration-200 font-semibold uppercase tracking-wider',
                    !live ? 'bg-background shadow-sm text-foreground border border-border/50' : 'text-muted-foreground hover:text-foreground'
                  )}
                  onClick={() => { setLive(false); setMaxApplications(500); }}
                  disabled={isRunning}
                >
                  Dry Run
                </button>
                <button
                  className={cn(
                    'flex-1 text-[11px] py-1.5 rounded-sm transition-all duration-200 font-semibold uppercase tracking-wider',
                    live ? 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20' : 'text-muted-foreground hover:text-foreground'
                  )}
                  onClick={() => { setLive(true); setMaxApplications(3); }}
                  disabled={isRunning}
                >
                  Live
                </button>
              </div>

              {/* Application ceiling */}
              <div className="flex flex-col gap-2">
                <label htmlFor="app-ceiling" className="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">Application Ceiling</label>
                <Input
                  id="app-ceiling"
                  type="number"
                  value={maxApplications}
                  onChange={e => setMaxApplications(Number(e.target.value))}
                  disabled={isRunning}
                  min={1}
                  max={1000}
                  className="h-9 text-sm"
                />
              </div>

              {/* Live-only options */}
              {live && (
                <div className="space-y-4 pt-4 border-t border-border">
                  <label className="flex items-start gap-3 cursor-pointer group">
                    <Checkbox
                      checked={canary}
                      onCheckedChange={v => setCanary(!!v)}
                      disabled={isRunning}
                      id="canary"
                      className="mt-0.5"
                    />
                    <div className="flex flex-col">
                      <span className="text-[13px] font-semibold text-foreground group-hover:text-foreground/80 transition-colors">Canary Release</span>
                      <span className="text-[11px] text-muted-foreground">Limits execution to exactly one live application for validation.</span>
                    </div>
                  </label>
                  <label className="flex items-start gap-3 cursor-pointer group">
                    <Checkbox
                      checked={forceLive}
                      onCheckedChange={v => setForceLive(!!v)}
                      disabled={isRunning}
                      id="force-live"
                      className="mt-0.5"
                    />
                    <div className="flex flex-col">
                      <span className="text-[13px] font-semibold text-foreground group-hover:text-foreground/80 transition-colors">Force Live</span>
                      <span className="text-[11px] text-muted-foreground">Bypasses provider cooldown constraints. Use with caution.</span>
                    </div>
                  </label>
                  <div className="flex items-start gap-3 p-3 bg-red-500/5 border border-red-500/20 rounded-md">
                    <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                    <p className="text-[11px] text-red-600 dark:text-red-400 font-medium leading-relaxed tracking-tight">
                      Live mode submits actual applications to external systems and consumes quotas. Proceed carefully.
                    </p>
                  </div>
                </div>
              )}

              {/* Launch */}
              <Button
                className={cn(
                  "w-full h-10 text-[13px] font-semibold tracking-wide transition-all",
                  live ? "bg-red-600 hover:bg-red-700 text-white" : ""
                )}
                onClick={handleLaunchClick}
                disabled={isRunning || launchMutation.isPending}
              >
                {launchMutation.isPending
                  ? 'Initializing Sequence…'
                  : isRunning
                  ? 'Sequence Running'
                  : live ? 'Execute Live Run' : 'Execute Dry Run'}
                {!isRunning && <Play className="w-4 h-4 ml-2 opacity-70" />}
              </Button>

            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Execute Live Application Sequence?"
        description="This will submit real applications to external providers. This action cannot be undone."
        confirmLabel="Execute Live Run"
        confirmVariant="destructive"
        onConfirm={handleConfirmedLaunch}
      />
    </div>
  );
}
