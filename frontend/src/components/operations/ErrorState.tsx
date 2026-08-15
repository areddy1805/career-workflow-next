import { cn } from '@/lib/utils';

// ─── ErrorState — the one error language (DESIGN.md §6, audit F4) ────────────
// Named problem + recovery action. Fault glyph + message; never silent empties.

export interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}

export function ErrorState({
  title = 'State unreachable',
  message,
  onRetry,
  retryLabel = 'Retry',
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn('flex items-start gap-3 rounded-md border border-failed/40 bg-surface px-4 py-3', className)}
      role="alert"
    >
      <svg
        width="13"
        height="13"
        viewBox="0 0 12 12"
        className="text-failed mt-0.5 shrink-0"
        aria-hidden="true"
      >
        <rect x="2" y="2" width="8" height="8" stroke="currentColor" fill="none" />
        <line x1="3.5" y1="3.5" x2="8.5" y2="8.5" stroke="currentColor" />
      </svg>
      <div className="min-w-0">
        <p className="text-[13px] font-semibold text-foreground leading-tight">{title}</p>
        <p className="text-meta text-muted-foreground mt-0.5 break-words">{message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="ml-auto shrink-0 rounded-sm border border-borderStrong px-2.5 py-1 text-[12px] font-medium text-foreground hover:bg-secondary transition-colors"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}
