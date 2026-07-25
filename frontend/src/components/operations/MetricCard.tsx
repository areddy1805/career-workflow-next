import React from "react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: React.ReactNode;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function MetricCard({ title, value, subtitle, icon, trend, className }: MetricCardProps) {
  return (
    <div className={cn("p-4 border border-border bg-card rounded-md shadow-card flex flex-col justify-between", className)}>
      <div className="flex items-center justify-between text-muted-foreground mb-2">
        <span className="text-xs font-medium uppercase tracking-wider">{title}</span>
        {icon && <span className="text-muted-foreground/60">{icon}</span>}
      </div>
      <div>
        <div className="text-2xl font-semibold text-foreground font-mono tracking-tight">{value}</div>
        {subtitle && (
          <div className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
            {trend === "up" && <span className="text-emerald-500">↑</span>}
            {trend === "down" && <span className="text-red-500">↓</span>}
            {subtitle}
          </div>
        )}
      </div>
    </div>
  );
}

export function MetricGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4", className)}>
      {children}
    </div>
  );
}
