import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchPipelineState, launchPipeline } from '@/lib/api';
import { Play, AlertTriangle, ArrowDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { RelativeTime } from '@/components/RelativeTime';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { StatusBadge } from '@/components/StatusBadge';

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

  const { data, isLoading, error } = useQuery({
    queryKey: ['pipeline_state'],
    queryFn: fetchPipelineState,
    refetchInterval: query => (query.state.data?.running ? 2000 : 8000),
  });

  const launchMutation = useMutation({
    mutationFn: launchPipeline,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline_state'] }),
  });

  // Auto-scroll log to bottom
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [data?.log, autoScroll]);

  // Detect manual scroll — disable auto-scroll
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
        Loading pipeline state…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-sm text-red-500">
        Failed to load pipeline state: {(error as Error).message}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background overflow-auto">

      {/* Page Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            Pipeline Control
            <StatusBadge status={isRunning ? 'RUNNING' : 'IDLE'} pulse={isRunning} />
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">Configure, execute, and observe the application engine.</p>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-6 p-6 max-w-[1600px]">

        {/* Left: Log viewer */}
        <div className="flex-[1.8] flex flex-col gap-0 min-w-0 border border-border/50 bg-card rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-border/50 bg-muted/10 flex items-center justify-between">
            <div>
              <h2 className="text-xs font-semibold">Live Output</h2>
              <p className="text-[10px] text-muted-foreground mt-0.5">Active launcher log</p>
            </div>
            {!autoScroll && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs gap-1.5"
                onClick={() => {
                  setAutoScroll(true);
                  logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                }}
              >
                <ArrowDown className="w-3 h-3" /> Scroll to bottom
              </Button>
            )}
          </div>
          <div
            ref={logContainerRef}
            onScroll={handleLogScroll}
            className="h-[480px] overflow-y-auto p-4 bg-[hsl(var(--background))] relative"
            style={{ fontFamily: 'JetBrains Mono, Fira Code, monospace' }}
          >
            <pre className="text-[12px] text-[hsl(var(--muted-foreground))] leading-relaxed whitespace-pre-wrap">
              {data?.log ?? 'No output yet. Launch the pipeline to begin.'}
            </pre>
            <div ref={logEndRef} />
          </div>
        </div>

        {/* Right: Telemetry + Config */}
        <div className="flex-1 flex flex-col gap-5 min-w-[300px]">

          {/* Telemetry */}
          <div className="border border-border/50 bg-card rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-border/50 bg-muted/10">
              <h2 className="text-xs font-semibold">Process Telemetry</h2>
            </div>
            <div className="grid grid-cols-2 gap-px bg-border/40">
              {[
                { label: 'Status',  value: isRunning ? 'Running' : 'Idle' },
                { label: 'PID',     value: state.pid ?? '—' },
                { label: 'Mode',    value: state.live ? 'Live' : 'Dry Run' },
                { label: 'Started', value: state.started_at
                    ? <RelativeTime date={state.started_at} />
                    : '—' },
              ].map(item => (
                <div key={item.label} className="bg-card px-4 py-3 flex flex-col gap-1">
                  <span className="text-[9px] uppercase font-mono font-semibold text-muted-foreground tracking-wider">{item.label}</span>
                  <span className="text-sm font-medium font-mono">{item.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Run Configuration */}
          <div className="border border-border/50 bg-card rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-border/50 bg-muted/10">
              <h2 className="text-xs font-semibold">Run Configuration</h2>
              <p className="text-[10px] text-muted-foreground mt-0.5">Safety-first execution controls</p>
            </div>
            <div className="p-4 space-y-4">

              {/* Mode toggle */}
              <div className="flex gap-1.5 p-1 bg-muted/40 rounded-md w-full border border-border/40">
                <button
                  className={cn(
                    'flex-1 text-xs py-1.5 rounded-sm transition-colors font-medium',
                    !live ? 'bg-background shadow-sm text-foreground border border-border/50' : 'text-muted-foreground hover:text-foreground'
                  )}
                  onClick={() => { setLive(false); setMaxApplications(500); }}
                  disabled={isRunning}
                >
                  Dry Run
                </button>
                <button
                  className={cn(
                    'flex-1 text-xs py-1.5 rounded-sm transition-colors font-medium',
                    live ? 'bg-background shadow-sm text-red-500 border border-red-500/30' : 'text-muted-foreground hover:text-foreground'
                  )}
                  onClick={() => { setLive(true); setMaxApplications(3); }}
                  disabled={isRunning}
                >
                  Live
                </button>
              </div>

              {/* Application ceiling */}
              <div className="flex flex-col gap-1.5">
                <label htmlFor="app-ceiling" className="text-xs font-medium">Application Ceiling</label>
                <Input
                  id="app-ceiling"
                  type="number"
                  value={maxApplications}
                  onChange={e => setMaxApplications(Number(e.target.value))}
                  disabled={isRunning}
                  min={1}
                  max={1000}
                  className="h-8 text-xs"
                />
              </div>

              {/* Live-only options */}
              {live && (
                <div className="space-y-3 pt-2 border-t border-border/40">
                  <label className="flex items-center gap-2.5 text-xs cursor-pointer">
                    <Checkbox
                      checked={canary}
                      onCheckedChange={v => setCanary(!!v)}
                      disabled={isRunning}
                      id="canary"
                    />
                    <span>
                      <span className="font-medium">Canary</span>
                      <span className="text-muted-foreground ml-1">— one live application</span>
                    </span>
                  </label>
                  <label className="flex items-center gap-2.5 text-xs cursor-pointer">
                    <Checkbox
                      checked={forceLive}
                      onCheckedChange={v => setForceLive(!!v)}
                      disabled={isRunning}
                      id="force-live"
                    />
                    <span>
                      <span className="font-medium">Force Live</span>
                      <span className="text-muted-foreground ml-1">— bypass cooldown</span>
                    </span>
                  </label>
                  <div className="flex items-start gap-2.5 p-3 bg-red-500/8 border border-red-500/20 rounded-md">
                    <AlertTriangle className="w-3.5 h-3.5 text-red-500 shrink-0 mt-0.5" />
                    <p className="text-xs text-red-500 font-medium leading-relaxed">
                      Live mode submits real applications and consumes quota.
                    </p>
                  </div>
                </div>
              )}

              {/* Launch */}
              <Button
                className="w-full h-9 text-sm font-semibold gap-2 mt-1"
                onClick={handleLaunchClick}
                disabled={isRunning || launchMutation.isPending}
              >
                {launchMutation.isPending
                  ? 'Starting…'
                  : isRunning
                  ? 'Pipeline Running'
                  : 'Launch Pipeline'}
                {!isRunning && <Play className="w-4 h-4" />}
              </Button>

            </div>
          </div>
        </div>
      </div>

      {/* Confirm live launch dialog */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Launch in Live Mode?"
        description="This will submit real job applications and consume quota. Live mode cannot be undone once started. Confirm only if you intend to apply."
        confirmLabel="Yes, Launch Live"
        confirmVariant="destructive"
        onConfirm={handleConfirmedLaunch}
      />
    </div>
  );
}
