import { formatDistanceToNow, format } from 'date-fns';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from './ui/tooltip';

interface RelativeTimeProps {
  date: string | Date;
  className?: string;
}

export function RelativeTime({ date, className }: RelativeTimeProps) {
  const parsedDate = new Date(date);
  
  // If invalid date, return raw
  if (isNaN(parsedDate.getTime())) return <span className={className}>{String(date)}</span>;

  const relative = formatDistanceToNow(parsedDate, { addSuffix: true });
  const absolute = format(parsedDate, 'PPpp');

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className={`cursor-help decoration-muted-foreground/30 underline decoration-dotted underline-offset-2 ${className}`}>
            {relative}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="text-xs font-mono">
          {absolute}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
