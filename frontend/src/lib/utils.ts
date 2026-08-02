import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSalary(min?: number, max?: number, currency?: string): string {
  if (!min && !max) return "Not specified";
  const curr = currency || "$";
  const formatNum = (num: number) => {
    if (num >= 1000) return `${(num / 1000).toFixed(0)}k`;
    return num.toString();
  };
  if (min && max) return `${curr}${formatNum(min)} - ${curr}${formatNum(max)}`;
  if (min) return `${curr}${formatNum(min)}+`;
  if (max) return `Up to ${curr}${formatNum(max)}`;
  return "Not specified";
}
