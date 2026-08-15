import React from 'react';
import { cn } from '@/lib/utils';

// ─── PageHeader — instrument header (DESIGN.md §7) ───────────────────────────
// One header idiom for all 24 routes: mono coordinate + title on one line
// (no kicker), subtitle below, actions right.

export interface PageHeaderProps {
  /** mono route coordinate, e.g. "01 · OVERVIEW" */
  coordinate: string;
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({ coordinate, title, subtitle, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('flex flex-wrap items-start gap-x-6 gap-y-3 mb-6', className)}>
      <div className="min-w-0">
        <h1 className="text-page text-foreground flex items-baseline gap-3">
          <span className="font-mono text-[10px] tracking-[0.1em] text-faint select-none" aria-hidden="true">
            {coordinate}
          </span>
          <span className="truncate">{title}</span>
        </h1>
        {subtitle && (
          <p className="text-meta text-muted-foreground mt-1.5 max-w-[65ch]">{subtitle}</p>
        )}
      </div>
      {actions && <div className="ml-auto flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
}
