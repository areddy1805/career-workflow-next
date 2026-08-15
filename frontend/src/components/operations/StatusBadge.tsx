import { StateMarker, type StateSemantic } from '@/components/operations/StateMarker';

// ─── Generic status → semantic state map ─────────────────────────────────────
// Thin wrapper over the single StateMarker grammar (DESIGN.md §4). Old props
// preserved so the 7 consuming pages inherit the Grid Control state language.

export type StatusType = "success" | "warning" | "error" | "info" | "neutral";

const TYPE_STATE: Record<StatusType, StateSemantic> = {
  success: 'healthy',
  warning: 'degraded',
  error: 'failed',
  info: 'pending',
  neutral: 'idle',
};

interface StatusBadgeProps {
  status: StatusType;
  label: string;
  className?: string;
  pulse?: boolean;
}

export function StatusBadge({ status, label, className, pulse }: StatusBadgeProps) {
  return (
    <StateMarker
      state={TYPE_STATE[status]}
      label={label}
      pulse={pulse}
      className={className}
    />
  );
}
