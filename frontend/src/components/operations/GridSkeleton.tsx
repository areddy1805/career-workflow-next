import { cn } from '@/lib/utils';

// ─── GridSkeleton — the one loading primitive (DESIGN.md §6, audit F2) ───────
// Structural skeleton: hairline panel + muted reading rows; one row carries a
// slow progress pulse on the affected segment. Reduced-motion → static.

export function GridSkeleton({
  rows = 4,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div
      className={cn('rounded-md border border-border bg-surface px-4 py-3 flex flex-col gap-2.5', className)}
      aria-busy="true"
      aria-label="Loading"
    >
      <div className="h-[10px] w-32 rounded-sm bg-muted" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <div
            className={cn(
              'h-[10px] rounded-sm bg-muted',
              i === 0 ? 'w-full pulse-live opacity-60' : 'w-full'
            )}
            style={i === 0 ? undefined : { width: `${92 - i * 7}%` }}
          />
        </div>
      ))}
    </div>
  );
}
