import { cn } from "@/lib/utils";

export type StatusType = "success" | "warning" | "error" | "info" | "neutral";

interface StatusBadgeProps {
  status: StatusType;
  label: string;
  className?: string;
  pulse?: boolean;
}

export function StatusBadge({ status, label, className, pulse }: StatusBadgeProps) {
  const baseClasses = "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border";
  
  const statusClasses = {
    success: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400",
    warning: "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
    error: "bg-red-500/10 text-red-600 border-red-500/20 dark:text-red-400",
    info: "bg-blue-500/10 text-blue-600 border-blue-500/20 dark:text-blue-400",
    neutral: "bg-muted text-muted-foreground border-border",
  };

  const dotClasses = {
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    error: "bg-red-500",
    info: "bg-blue-500",
    neutral: "bg-muted-foreground",
  };

  return (
    <span className={cn(baseClasses, statusClasses[status], className)}>
      <span className={cn("w-1.5 h-1.5 rounded-full", dotClasses[status], pulse && "pulse-green")} />
      {label}
    </span>
  );
}
