import React from 'react';
import { cn } from '@/lib/utils';

// ─── EmptyState — the one empty-state language (DESIGN.md §6) ────────────────
// Unlit-bus motif + one-line title + optional single action. Same component on
// every surface.

export interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn('flex flex-col items-center justify-center text-center gap-1.5 px-6 py-10', className)}
      role="status"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 12 12"
        className="text-faint mb-1"
        aria-hidden="true"
      >
        <line x1="1" y1="6" x2="11" y2="6" stroke="currentColor" strokeDasharray="2 3" />
        <circle cx="6" cy="6" r="1.5" fill="currentColor" />
      </svg>
      <p className="text-emphasis text-muted-foreground">{title}</p>
      {description && <p className="text-meta text-faint max-w-[52ch]">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
