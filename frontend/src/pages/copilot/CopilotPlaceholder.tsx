import type { LucideIcon } from 'lucide-react';

/**
 * Shared empty-state shell for the Copilot surface placeholders (CP-0-05).
 * Non-functional until the owning phase lands.
 */
export default function CopilotPlaceholder({
  icon: Icon,
  title,
  subtitle,
  note,
}: {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  note: string;
}) {
  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <Icon className="w-4 h-4 text-primary" /> {title}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-muted/5 p-6 flex items-center justify-center">
        <div className="max-w-sm w-full bg-card border border-border/50 rounded-xl p-8 text-center space-y-3 shadow-sm">
          <Icon className="w-8 h-8 text-muted-foreground/40 mx-auto" aria-hidden="true" />
          <p className="text-sm font-medium">{title}</p>
          <p className="text-xs text-muted-foreground">{note}</p>
        </div>
      </div>
    </div>
  );
}
