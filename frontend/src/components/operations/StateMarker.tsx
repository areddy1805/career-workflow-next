import { cn } from '@/lib/utils';

// ─── Grid Control status grammar (DESIGN.md §4) ───────────────────────────────
// Status is symbol shape + line form + text label; hue only confirms.
// The glyphs are breaker/state symbols: filled = closed/live, open = gated,
// dashed = pending, struck = failed, latched = terminal, tagged = manual hold.

export type StateSemantic =
  | 'healthy'
  | 'running'
  | 'degraded'
  | 'blocked'
  | 'pending'
  | 'manual'
  | 'failed'
  | 'terminal'
  | 'idle'
  | 'unknown';

export type LineForm = 'solid' | 'dashed' | 'dotted' | 'half' | 'struck' | 'doubled';

export const STATE_HUE: Record<StateSemantic, string> = {
  healthy: 'text-healthy',
  running: 'text-running',
  degraded: 'text-degraded',
  blocked: 'text-blocked',
  pending: 'text-pending',
  manual: 'text-manual',
  failed: 'text-failed',
  terminal: 'text-terminal',
  idle: 'text-faint',
  unknown: 'text-faint',
};

const GLYPH: Record<StateSemantic, React.ReactNode> = {
  // closed breaker — live/complete
  healthy: <rect x="2" y="2" width="8" height="8" fill="currentColor" />,
  // closed breaker, live
  running: <rect x="2" y="2" width="8" height="8" fill="currentColor" />,
  // half-open breaker — degraded
  degraded: (
    <>
      <rect x="2" y="2" width="4" height="8" fill="currentColor" />
      <rect x="6" y="2" width="4" height="8" stroke="currentColor" fill="none" />
    </>
  ),
  // open breaker — gated
  blocked: <rect x="2" y="2" width="8" height="8" stroke="currentColor" fill="none" />,
  // open breaker, scheduled
  pending: <rect x="2" y="2" width="8" height="8" stroke="currentColor" strokeDasharray="2 2" fill="none" />,
  // open breaker + tag plate — human hold
  manual: (
    <>
      <rect x="2" y="2" width="8" height="8" stroke="currentColor" fill="none" />
      <rect x="8" y="0.5" width="3.5" height="3.5" fill="currentColor" />
    </>
  ),
  // faulted — failed
  failed: (
    <>
      <rect x="2" y="2" width="8" height="8" stroke="currentColor" fill="none" />
      <line x1="3.5" y1="3.5" x2="8.5" y2="8.5" stroke="currentColor" />
    </>
  ),
  // latched closed — terminal/recorded
  terminal: (
    <>
      <rect x="2" y="3" width="8" height="2.5" fill="currentColor" />
      <rect x="2" y="6.5" width="8" height="2.5" fill="currentColor" opacity="0.55" />
    </>
  ),
  // unlit bus — idle
  idle: <circle cx="6" cy="6" r="3.5" stroke="currentColor" fill="none" opacity="0.7" />,
  // unread state — unknown
  unknown: (
    <path d="M6 1.5 L10.5 6 L6 10.5 L1.5 6 Z" stroke="currentColor" strokeDasharray="2 2" fill="none" />
  ),
};

export interface StateMarkerProps {
  state: StateSemantic;
  label?: string;
  /** pulse only for live states (running / live healthy) */
  pulse?: boolean;
  size?: 'sm' | 'md';
  className?: string;
  /** render the label hidden (sr-only) but present for AT */
  hideLabel?: boolean;
  id?: string;
}

export function StateMarker({
  state,
  label,
  pulse,
  size = 'sm',
  className,
  hideLabel,
  id,
}: StateMarkerProps) {
  const dim = size === 'sm' ? 11 : 13;
  return (
    <span className={cn('inline-flex items-center gap-1.5 align-middle', className)}>
      <svg
        width={dim}
        height={dim}
        viewBox="0 0 12 12"
        className={cn('shrink-0 state-snap', STATE_HUE[state], (pulse || state === 'running') && 'pulse-live')}
        aria-hidden="true"
        data-state={state}
        id={id}
      >
        {GLYPH[state]}
      </svg>
      {label && (
        <span
          className={cn(
            'font-mono text-[10px] uppercase tracking-[0.08em] leading-none text-muted-foreground whitespace-nowrap',
            hideLabel && 'sr-only'
          )}
        >
          {label}
        </span>
      )}
    </span>
  );
}
