import React from "react";
import { cn } from "@/lib/utils";

interface StatRowProps {
  label: string;
  value: React.ReactNode;
  className?: string;
  valueClassName?: string;
}

export function StatRow({ label, value, className, valueClassName }: StatRowProps) {
  return (
    <div className={cn("flex items-baseline justify-between py-2.5 border-b border-border/50 last:border-0 text-xs gap-4", className)}>
      <span className="text-muted-foreground shrink-0 font-medium tracking-tight">{label}</span>
      <span className={cn("font-semibold text-right truncate text-foreground", valueClassName)}>{value}</span>
    </div>
  );
}
