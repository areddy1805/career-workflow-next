import { useToasts, type ToastKind } from '@/lib/toast';
import { cn } from '@/lib/utils';

// ─── Toaster — the toast channel's renderer (audit F1) ───────────────────────
// Mount once in the shell. Fixed bottom-right stack, aria-live polite.
// Kind is encoded by glyph + label text, not color alone.

const KIND_GLYPH: Record<ToastKind, string> = {
  success: '●',
  error: '✕',
  info: '–',
};

export function Toaster() {
  const { toasts, dismiss } = useToasts();
  if (toasts.length === 0) return null;
  return (
    <div
      className="fixed bottom-4 right-4 z-[90] flex flex-col gap-2 w-[320px] max-w-[calc(100vw-2rem)]"
      aria-live="polite"
      role="status"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            'flex items-start gap-2.5 rounded-md border bg-surface-raised px-3.5 py-2.5 text-[13px] text-foreground shadow-none',
            t.kind === 'success' && 'border-healthy/50',
            t.kind === 'error' && 'border-failed/50',
            t.kind === 'info' && 'border-border'
          )}
        >
          <span
            className={cn(
              'font-mono text-[11px] leading-[1.4] mt-px shrink-0',
              t.kind === 'success' && 'text-healthy',
              t.kind === 'error' && 'text-failed',
              t.kind === 'info' && 'text-muted-foreground'
            )}
            aria-hidden="true"
          >
            {KIND_GLYPH[t.kind]}
          </span>
          <span className="flex-1 min-w-0 break-words">{t.message}</span>
          <button
            type="button"
            onClick={() => dismiss(t.id)}
            aria-label="Dismiss notification"
            className="shrink-0 text-faint hover:text-foreground transition-colors px-1"
          >
            <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true">
              <line x1="2" y1="2" x2="10" y2="10" stroke="currentColor" />
              <line x1="10" y1="2" x2="2" y2="10" stroke="currentColor" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
