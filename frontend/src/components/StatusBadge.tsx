import { cn } from '@/lib/utils';

// ─── Global Status Color Semantics ────────────────────────────────────────────
//   Emerald  → Applied, Success, Active, Healthy, Offer
//   Red      → Rejected, Failed, Error
//   Blue     → Running, In Progress, Interview, Shortlisted
//   Amber    → Pending, Warning, Degraded, Stale
//   Purple   → Manual Review
//   Gray     → Dry Run, Skipped, Idle, Archived, Unknown
// ─────────────────────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
  // ── Emerald: completion / success ──
  APPLIED:       'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  SUBMITTED:     'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  SUCCESS:       'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  HEALTHY:       'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  ACTIVE:        'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  OFFER:         'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  LIVE:          'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',

  // ── Red: failure / rejection ──
  REJECTED:      'bg-red-500/10 text-red-600 dark:text-red-400',
  FAILED:        'bg-red-500/10 text-red-600 dark:text-red-400',
  ERROR:         'bg-red-500/10 text-red-600 dark:text-red-400',
  ARCHIVED:      'bg-red-500/10 text-red-600 dark:text-red-400',

  // ── Blue: in-flight / progress ──
  RUNNING:       'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  IN_PROGRESS:   'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  INTERVIEW:     'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  SHORTLISTED:   'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  OPENED:        'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  VIEWED:        'bg-blue-500/10 text-blue-600 dark:text-blue-400',

  // ── Amber: waiting / caution ──
  PENDING:             'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  WARNING:             'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  DEGRADED:            'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  STALE:               'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  DRY:                 'bg-amber-500/10 text-amber-600 dark:text-amber-400',

  // ── Purple: human action required ──
  MANUAL_REVIEW: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  MANUAL:        'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  REVIEW:        'bg-purple-500/10 text-purple-600 dark:text-purple-400',

  // ── Gray: neutral / suppressed ──
  DRY_RUN_SUPPRESSED: 'bg-muted text-muted-foreground',
  DRY_RUN:       'bg-muted text-muted-foreground',
  SKIPPED:       'bg-muted text-muted-foreground',
  IDLE:          'bg-muted text-muted-foreground',
  UNKNOWN:       'bg-muted text-muted-foreground',
  NEW:           'bg-muted text-muted-foreground',
};

// Human-readable label overrides — keep these minimal
const STATUS_LABELS: Record<string, string> = {
  DRY_RUN_SUPPRESSED: 'Dry Run',
  IN_PROGRESS:        'Running',
  MANUAL_REVIEW:      'Review',
};

interface StatusBadgeProps {
  status: string;
  className?: string;
  /** Adds a pulsing animation — use only for actively running states */
  pulse?: boolean;
}

export function StatusBadge({ status, className, pulse }: StatusBadgeProps) {
  const upper = (status || 'UNKNOWN').toUpperCase();
  const styles = STATUS_STYLES[upper] ?? 'bg-zinc-500/8 text-zinc-500 border-zinc-500/20';
  const label  = STATUS_LABELS[upper] ?? status;
  const shouldPulse = pulse && (upper === 'RUNNING' || upper === 'IN_PROGRESS');

  return (
    <span
      className={cn(
        'inline-flex items-center px-1.5 py-0.5 rounded',
        'text-[10px] font-semibold font-mono uppercase tracking-wide leading-none whitespace-nowrap',
        styles,
        shouldPulse && 'animate-pulse',
        className,
      )}
    >
      {label}
    </span>
  );
}
