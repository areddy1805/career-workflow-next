import { useState, useEffect, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { launchPipeline } from '@/lib/api';
import { usePipelineState } from '@/lib/hooks';
import { Play, AlertTriangle, ArrowDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { RelativeTime } from '@/components/RelativeTime';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { PageHeader } from '@/components/operations/PageHeader';
import { Panel, PanelHeader } from '@/components/operations/Panel';
import { GridSkeleton } from '@/components/operations/GridSkeleton';
import { ErrorState } from '@/components/operations/ErrorState';
import { StateMarker } from '@/components/operations/StateMarker';

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

  const { data, isLoading, error, refetch } = usePipelineState();

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

  // Mode toggle — radiogroup semantics (audit A3): arrow-key navigable
  const onModeKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    setLive(e.key === 'ArrowRight');
    setMaxApplications(e.key === 'ArrowRight' ? 3 : 500);
  };

  const isRunning = data?.running ?? false;
  const state     = data?.state   ?? {};

  if (isLoading && !data) {
    return (
      <div className="h-full flex flex-col">
        <PageHeader coordinate="01 · 02" title="Pipeline Control" subtitle="Configure, execute, and observe the application engine." />
        <GridSkeleton rows={5} className="flex-1" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex flex-col">
        <PageHeader coordinate="01 · 02" title="Pipeline Control" subtitle="Configure, execute, and observe the application engine." />
        <ErrorState
          title="Pipeline state unreachable"
          message={(error as Error).message}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        coordinate="01 · 02"
        title="Pipeline Control"
        subtitle="Configure, execute, and observe the application engine."
        actions={
          <StateMarker
            state={isRunning ? 'running' : 'idle'}
            label={isRunning ? 'RUNNING' : 'IDLE'}
            pulse={isRunning}
          />
        }
      />

      <div className="flex flex-col lg:flex-row gap-6 pb-6 lg:flex-1 lg:min-h-0">
        {/* Left: Live output — console terminal (§3, audit C4) */}
        <Panel className="flex-[1.8] flex flex-col min-w-0 overflow-hidden">
          <PanelHeader
            index="L1"
            title="Live Output"
            actions={
              !autoScroll && (
                <button
                  type="button"
                  className="text-[10px] font-medium tracking-tight text-foreground hover:text-foreground/70 transition-colors flex items-center gap-1.5"
                  onClick={() => {
                    setAutoScroll(true);
                    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                  }}
                >
                  <ArrowDown className="w-3 h-3" /> Scroll to bottom
                </button>
              )
            }
          />
          <div
            ref={logContainerRef}
            onScroll={handleLogScroll}
            className="flex-1 min-h-[280px] lg:min-h-0 overflow-y-auto bg-console p-4"
          >
            <pre className="text-[11px] font-mono text-console-foreground/75 leading-relaxed whitespace-pre-wrap">
              {data?.log ?? 'No output yet. Launch the pipeline to begin.'}
            </pre>
            <div ref={logEndRef} />
          </div>
        </Panel>

        {/* Right: Telemetry + Configuration */}
        <div className="flex-1 flex flex-col gap-6 min-w-[300px]">

          {/* Telemetry — process state readout */}
          <Panel>
            <PanelHeader index="T1" title="Telemetry" />
            <div className="grid grid-cols-2 gap-px bg-border/60">
              {[
                { label: 'Status',  value: isRunning ? 'Running' : 'Idle' },
                { label: 'PID',     value: state.pid ?? '—' },
                { label: 'Mode',    value: state.live ? 'Live' : 'Dry Run' },
                { label: 'Started', value: state.started_at
                    ? <RelativeTime date={state.started_at} />
                    : '—' },
              ].map(item => (
                <div key={item.label} className="bg-surface px-4 py-3 flex flex-col gap-1.5">
                  <span className="font-mono text-[9px] uppercase font-semibold text-muted-foreground tracking-widest">{item.label}</span>
                  <span className="text-sm font-medium tracking-tight text-foreground tabular-nums">{item.value}</span>
                </div>
              ))}
            </div>
          </Panel>

          {/* Run configuration */}
          <Panel>
            <PanelHeader index="C1" title="Configuration" />
            <div className="p-5 space-y-5">

              {/* Mode toggle — radiogroup (audit A3) */}
              <div
                role="radiogroup"
                aria-label="Run mode"
                onKeyDown={onModeKeyDown}
                className="grid grid-cols-2 gap-1 p-1 bg-muted/50 rounded-md w-full border border-border"
              >
                <button
                  role="radio"
                  aria-checked={!live}
                  className={cn(
                    'flex-1 text-[11px] py-1.5 rounded-sm transition-all duration-150 font-semibold uppercase tracking-wider focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    !live ? 'bg-background text-foreground border border-borderStrong shadow-none' : 'text-muted-foreground hover:text-foreground border border-transparent'
                  )}
                  onClick={() => { setLive(false); setMaxApplications(500); }}
                  disabled={isRunning}
                >
                  Dry Run
                </button>
                <button
                  role="radio"
                  aria-checked={live}
                  className={cn(
                    'flex-1 text-[11px] py-1.5 rounded-sm transition-all duration-150 font-semibold uppercase tracking-wider focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    live ? 'bg-failed/10 text-failed border border-failed/40' : 'text-muted-foreground hover:text-foreground border border-transparent'
                  )}
                  onClick={() => { setLive(true); setMaxApplications(3); }}
                  disabled={isRunning}
                >
                  Live
                </button>
              </div>

              {/* Application ceiling */}
              <div className="flex flex-col gap-2">
                <label htmlFor="app-ceiling" className="font-mono text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">Application Ceiling</label>
                <Input
                  id="app-ceiling"
                  type="number"
                  value={maxApplications}
                  onChange={e => setMaxApplications(Number(e.target.value))}
                  disabled={isRunning}
                  min={1}
                  max={1000}
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
                  <div className="flex items-start gap-3 p-3 bg-failed/5 border border-failed/30 rounded-md">
                    <AlertTriangle className="w-4 h-4 text-failed shrink-0 mt-0.5" />
                    <p className="text-[11px] text-failed font-medium leading-relaxed tracking-tight">
                      Live mode submits actual applications to external systems and consumes quotas. Proceed carefully.
                    </p>
                  </div>
                </div>
              )}

              {/* Launch — destructive when live; gated by ConfirmDialog */}
              <Button
                variant={live ? 'destructive' : 'default'}
                className={cn('w-full h-10 text-[13px] font-semibold tracking-wide')}
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
          </Panel>
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
