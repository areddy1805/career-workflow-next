import React from 'react';
import { cn } from '@/lib/utils';

// ─── Panel — the one container (DESIGN.md §3, §7) ────────────────────────────
// Hairline border, surface step, 6px radius. No shadows, no nesting rules
// beyond common sense. Replaces the hand-rolled card idiom.

export function Panel({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn('rounded-md border border-border bg-surface', className)}
      {...props}
    >
      {children}
    </section>
  );
}

export interface PanelHeaderProps {
  /** mono instrument index, e.g. "02" — sequence carries location info */
  index?: string;
  title: string;
  actions?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}

export function PanelHeader({ index, title, actions, className }: PanelHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-2.5 border-b border-border min-h-[38px]',
        className
      )}
    >
      {index && (
        <span className="font-mono text-[10px] tracking-[0.1em] text-faint select-none" aria-hidden="true">
          {index}
        </span>
      )}
      <h2 className="text-[13px] font-semibold tracking-tight text-foreground leading-none truncate">
        {title}
      </h2>
      <div className="ml-auto flex items-center gap-2 shrink-0">{actions}</div>
    </div>
  );
}
