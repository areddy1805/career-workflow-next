import { StateMarker, type StateSemantic } from '@/components/operations/StateMarker';

// ─── Legacy keyword → semantic state map ─────────────────────────────────────
// Both incumbent badge systems now render through the one StateMarker grammar
// (DESIGN.md §4). This file keeps its old props; the keyword legend lives here
// so consuming pages inherit the Grid Control state language unchanged.

const KEYWORD_STATE: Record<string, StateSemantic> = {
  // healthy / complete
  APPLIED: 'healthy',
  SUBMITTED: 'healthy',
  SUCCESS: 'healthy',
  HEALTHY: 'healthy',
  ACTIVE: 'healthy',
  OFFER: 'healthy',
  LIVE: 'healthy',
  // in-flight
  RUNNING: 'running',
  IN_PROGRESS: 'running',
  INTERVIEW: 'running',
  SHORTLISTED: 'running',
  // waiting / scheduled
  PENDING: 'pending',
  VIEWED: 'pending',
  OPENED: 'pending',
  NEW: 'pending',
  // degraded / caution
  WARNING: 'degraded',
  DEGRADED: 'degraded',
  STALE: 'degraded',
  // gated / suppressed
  BLOCKED: 'blocked',
  DRY: 'blocked',
  DRY_RUN: 'blocked',
  DRY_RUN_SUPPRESSED: 'blocked',
  SKIPPED: 'blocked',
  // human action required
  MANUAL_REVIEW: 'manual',
  MANUAL: 'manual',
  REVIEW: 'manual',
  // failure
  REJECTED: 'failed',
  FAILED: 'failed',
  ERROR: 'failed',
  // terminal / recorded
  ARCHIVED: 'terminal',
  TERMINAL: 'terminal',
  // quiet
  IDLE: 'idle',
  UNKNOWN: 'unknown',
};

const STATE_LABELS: Record<string, string> = {
  DRY_RUN_SUPPRESSED: 'Dry Run',
  IN_PROGRESS: 'Running',
  MANUAL_REVIEW: 'Review',
  TERMINAL_FAILURE: 'Terminal',
  RECOVERABLE_FAILURE: 'Failed',
};

interface StatusBadgeProps {
  status: string;
  className?: string;
  /** Adds a pulsing animation — use only for actively running states */
  pulse?: boolean;
}

export function StatusBadge({ status, className, pulse }: StatusBadgeProps) {
  const upper = (status || 'UNKNOWN').toUpperCase();
  const state = KEYWORD_STATE[upper] ?? 'unknown';
  const label = STATE_LABELS[upper] ?? status;

  return (
    <StateMarker
      state={state}
      label={label}
      pulse={pulse}
      className={className}
    />
  );
}
