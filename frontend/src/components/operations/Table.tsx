import React from 'react';
import { cn } from '@/lib/utils';

// ─── Table — the one operational table grammar (DESIGN.md §7, audit X2) ──────
// Semantic <table> with hairline rows and tabular numerals. The Ledger migrates
// to TanStack in a later pass; this shared primitive owns the visual grammar.

export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto">
      <table
        className={cn('w-full text-body text-foreground border-collapse', className)}
        {...props}
      />
    </div>
  );
}

export function THead({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn('border-b border-border bg-muted/40', className)}
      {...props}
    />
  );
}

export function TBody({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn('divide-y divide-border/70', className)} {...props} />;
}

export function TH({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={cn(
        'px-4 py-2 text-left font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground font-medium whitespace-nowrap',
        className
      )}
      {...props}
    />
  );
}

export function TR({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn('hover:bg-muted/30 transition-colors', className)}
      {...props}
    />
  );
}

export function TD({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={cn('px-4 py-2.5 align-middle text-body tabular whitespace-nowrap', className)}
      {...props}
    />
  );
}
