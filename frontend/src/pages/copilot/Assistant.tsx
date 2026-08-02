import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ExternalLink,
  Eye,
  Flag,
  HelpCircle,
  Loader2,
  Monitor,
  Pencil,
  ShieldAlert,
  Upload,
  X,
} from 'lucide-react';
import * as api from '@/lib/api/copilot';
import type {
  AuditAction,
  BrowserSession,
  Checkpoint,
  FieldFill,
  FormModel,
  GuidancePlan,
  TypedField,
} from '@/lib/api/copilot';
import { useSession } from '@/lib/hooks';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

/**
 * Copilot Assistant panel (docs/application_copilot/07_UI.md §3.4, CP-6-04).
 *
 * The controlled browser runs in the backend process as a visible desktop
 * window (ADR-003) — it is NOT the user's tab, so it cannot be iframed into
 * this page. We render a live status card (url/title/state) + an "Open
 * externally" link (window.open semantics) instead.
 *
 * Flow: open the browser session for this workspace session → drive the
 * §6 fill pass (one browserFill per field, per tick) → surface the open
 * §7 checkpoint gate → human Continue / Edit field (Answer Bank
 * confirmAnswer + re-fill) / Take over → once every field is filled and no
 * gates remain (and the browser is still opened + auto_fillable), advance
 * the session FORM_FILLED so the workspace wizard's submit step unlocks.
 *
 * Takeover (04 §7: the assistant annotates but never fights back): a 409
 * "human has taken over" from any driving call — or the Take over button —
 * switches the panel to guidance-only mode (browserGuidance steps).
 */

// ─── Deterministic fill-status mapping (04 §6 decision matrix) ─────────────

type FillStatus =
  | 'pending'
  | 'filled'
  | 'flagged'
  | 'asked'
  | 'unknown'
  | 'sensitive'
  | 'upload';

function fillStatus(fill: FieldFill | undefined, field: TypedField): FillStatus {
  if (!fill) return 'pending';
  // Sensitive fields always stage (reason text is the only frontend signal).
  if (fill.reason.includes('sensitive')) return 'sensitive';
  if (field.kind === 'upload') return 'upload';
  if (!fill.filled && fill.confidence == null) return 'unknown';
  if (!fill.filled) return 'asked';
  return fill.confidence != null && fill.confidence >= 0.95 ? 'filled' : 'flagged';
}

const STATUS_META: Record<FillStatus, { label: string; className: string }> = {
  pending: { label: 'pending', className: 'border-border text-muted-foreground' },
  filled: {
    label: 'filled',
    className: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  },
  flagged: {
    label: 'flagged',
    className: 'border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400',
  },
  asked: {
    label: 'asked',
    className: 'border-blue-500/40 bg-blue-500/10 text-blue-600 dark:text-blue-400',
  },
  unknown: {
    label: 'unknown',
    className: 'border-border bg-muted/40 text-muted-foreground',
  },
  sensitive: {
    label: 'sensitive',
    className: 'border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-400',
  },
  upload: {
    label: 'upload',
    className: 'border-violet-500/40 bg-violet-500/10 text-violet-600 dark:text-violet-400',
  },
};

const SOURCE_CHIP: Record<string, string> = {
  stored: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  deterministic:
    'border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400',
  llm: 'border-violet-500/40 bg-violet-500/10 text-violet-600 dark:text-violet-400',
  manual: 'border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400',
};

const CHECKPOINT_META: Record<string, { label: string; icon: typeof Flag }> = {
  flag: { label: 'Flagged', icon: Flag },
  ask: { label: 'Ask', icon: HelpCircle },
  unknown: { label: 'Unknown', icon: Eye },
  upload: { label: 'Upload', icon: Upload },
  sensitive: { label: 'Sensitive', icon: ShieldAlert },
};

function browserStateLabel(state: string | undefined): string {
  return state ?? 'unknown';
}

// ─── Panel state ───────────────────────────────────────────────────────────

type Phase =
  | 'loading' // session fetch in flight
  | 'opening' // browser open / first form read
  | 'filling' // driving the fill pass (assistant in control)
  | 'checkpoint' // a gate is open, waiting on the human
  | 'guidance' // human took over; annotate-only
  | 'done' // FORM_FILLED advanced (or already filled)
  | 'idle'; // stopped (terminal / fatal error)

interface PanelState {
  phase: Phase;
  browser: BrowserSession | null;
  form: FormModel | null;
  fills: Record<string, FieldFill>;
  checkpoint: Checkpoint | null;
  guidance: GuidancePlan | null;
  actions: AuditAction[];
  error: string | null;
  busy: string | null; // key of the in-flight mutation (button disable)
  editingFieldId: string | null;
  editValue: string;
}

const INITIAL_STATE: PanelState = {
  phase: 'loading',
  browser: null,
  form: null,
  fills: {},
  checkpoint: null,
  guidance: null,
  actions: [],
  error: null,
  busy: null,
  editingFieldId: null,
  editValue: '',
};

// ─── Small presentational pieces ───────────────────────────────────────────

function StateBadge({ state }: { state: string | undefined }) {
  const meta: Record<string, string> = {
    opened: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    taken_over:
      'border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400',
    aborted: 'border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400',
  };
  return (
    <Badge variant="outline" className={meta[state ?? ''] ?? 'border-border text-muted-foreground'}>
      {browserStateLabel(state)}
    </Badge>
  );
}

function ConfidenceBar({ value }: { value: number | null }) {
  const pct = value == null ? 0 : Math.round(value * 100);
  return (
    <div
      role="progressbar"
      aria-label="fill confidence"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      title={value == null ? 'No confidence (unresolved)' : `${pct}% confidence`}
      className="h-1.5 w-full rounded-full bg-muted"
    >
      <div
        className={cn(
          'h-full rounded-full',
          value == null
            ? 'bg-muted-foreground/30'
            : pct >= 95
              ? 'bg-emerald-500'
              : pct >= 80
                ? 'bg-amber-500'
                : 'bg-sky-500',
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function SourceChip({ source }: { source: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium',
        SOURCE_CHIP[source] ?? 'border-border text-muted-foreground',
      )}
    >
      {source}
    </span>
  );
}

function ErrorBanner({
  message,
  onDismiss,
  onRetry,
}: {
  message: string;
  onDismiss?: () => void;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-500/5 px-3 py-2 text-xs text-red-600 dark:text-red-400"
    >
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <p className="flex-1">{message}</p>
      {onRetry ? (
        <Button type="button" variant="ghost" size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
      {onDismiss ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      ) : null}
    </div>
  );
}

// ─── Live browser status card ──────────────────────────────────────────────

function StatusCard({
  browser,
  form,
  phase,
}: {
  browser: BrowserSession | null;
  form: FormModel | null;
  phase: Phase;
}) {
  // The Playwright browser lives in the backend process as a visible desktop
  // window (ADR-003) — it is not this page's tab, so it cannot be iframed.
  // The live view is therefore a status card + an external-open link.
  const displayState = phase === 'guidance' ? 'taken_over' : browser?.state;
  const pageUrl = browser?.page_url ?? null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Monitor className="h-4 w-4 text-primary" aria-hidden="true" />
          Controlled browser
          <span className="ml-auto">
            <StateBadge state={displayState} />
          </span>
        </CardTitle>
        <CardDescription>
          Visible Playwright window in the backend process (ADR-003) — not
          iframable; use the link below to watch it on your screen.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-xs">
          <dt className="text-muted-foreground">Page</dt>
          <dd className="min-w-0 truncate font-mono" title={pageUrl ?? undefined}>
            {pageUrl ?? '—'}
          </dd>
          <dt className="text-muted-foreground">Title</dt>
          <dd className="truncate" title={browser?.title ?? undefined}>
            {browser?.title ?? '—'}
          </dd>
          <dt className="text-muted-foreground">ATS</dt>
          <dd>{form?.ats_type ?? '—'}</dd>
          <dt className="text-muted-foreground">Pages</dt>
          <dd>{form?.pages ?? '—'}</dd>
          <dt className="text-muted-foreground">Auto-fill</dt>
          <dd>
            {form == null
              ? '—'
              : form.auto_fillable
                ? 'available'
                : 'unavailable'}
          </dd>
        </dl>
        {pageUrl ? (
          <Button asChild variant="outline" size="sm">
            <a href={pageUrl} target="_blank" rel="noopener noreferrer">
              Open externally
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            </a>
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">
            No page URL yet — the browser may still be loading.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Checkpoint banner ─────────────────────────────────────────────────────

function CheckpointBanner({
  checkpoint,
  fields,
  busy,
  onContinue,
  onEdit,
  onTakeOver,
}: {
  checkpoint: Checkpoint;
  fields: TypedField[];
  busy: string | null;
  onContinue: () => void;
  onEdit: (fieldId: string) => void;
  onTakeOver: () => void;
}) {
  const byId = new Map(fields.map((f) => [f.field_id, f]));
  const submitGate = checkpoint.type === 'submit';
  return (
    <section
      aria-label="Checkpoint"
      className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3"
    >
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-amber-500" aria-hidden="true" />
        <h3 className="text-sm font-semibold">
          {submitGate
            ? 'Checkpoint: submit gate'
            : `Checkpoint: ${checkpoint.type.replace('_', ' ')}`}
        </h3>
        <Badge variant="outline" className="ml-auto border-border text-muted-foreground">
          {checkpoint.dismissible ? 'dismissible' : 'not dismissible'}
        </Badge>
      </div>

      {checkpoint.pending.length > 0 ? (
        <ul className="mt-2 space-y-2">
          {checkpoint.pending.map((item) => {
            const field = byId.get(item.field_id);
            const meta = CHECKPOINT_META[item.type] ?? { label: item.type, icon: Flag };
            const Icon = meta.icon;
            return (
              <li
                key={item.field_id}
                className="flex items-start gap-2 rounded-md border border-border/60 bg-background/60 px-2 py-1.5 text-xs"
              >
                <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">
                    {field?.label ?? item.field_id}
                    <span className="ml-1.5 text-muted-foreground">({meta.label})</span>
                  </p>
                  <p className="text-muted-foreground">{item.reason}</p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 shrink-0"
                  onClick={() => onEdit(item.field_id)}
                  disabled={busy != null}
                  aria-label={`Edit field ${field?.label ?? item.field_id}`}
                >
                  <Pencil className="h-3 w-3" aria-hidden="true" />
                  Edit field
                </Button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">
          No pending items — this gate is informational. Confirm to continue.
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          onClick={onContinue}
          disabled={busy != null}
        >
          {busy === 'confirm' ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          Continue
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onTakeOver} disabled={busy != null}>
          Take over
        </Button>
      </div>
    </section>
  );
}

// ─── Field rail ────────────────────────────────────────────────────────────

function FieldRow({
  field,
  fill,
  editing,
  editValue,
  busy,
  onEdit,
  onEditChange,
  onSave,
  onCancel,
}: {
  field: TypedField;
  fill: FieldFill | undefined;
  editing: boolean;
  editValue: string;
  busy: string | null;
  onEdit: (fieldId: string) => void;
  onEditChange: (value: string) => void;
  onSave: (fieldId: string) => void;
  onCancel: () => void;
}) {
  const status = fillStatus(fill, field);
  const meta = STATUS_META[status];
  const editable = fill != null && typeof fill.resolution?.question_fp === 'string';

  return (
    <li className="space-y-1.5 rounded-md border border-border/60 bg-background/60 px-2.5 py-2">
      <div className="flex items-center gap-2">
        <p className="min-w-0 flex-1 truncate text-xs font-medium" title={field.label}>
          {field.label}
          {field.required ? (
            <span className="text-red-500" aria-hidden="true">
              {' '}
              *
            </span>
          ) : null}
        </p>
        <Badge variant="outline" className={cn('shrink-0', meta.className)}>
          {meta.label}
        </Badge>
        {fill ? <SourceChip source={fill.source} /> : null}
      </div>
      <div className="flex items-center gap-2">
        <ConfidenceBar value={fill?.confidence ?? null} />
        {editable && status !== 'filled' ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0"
            onClick={() => onEdit(field.field_id)}
            disabled={busy != null}
            aria-label={`Edit ${field.label}`}
            title={fill?.reason}
          >
            <Pencil className="h-3 w-3" aria-hidden="true" />
          </Button>
        ) : null}
      </div>
      {fill && status !== 'filled' && fill.reason ? (
        <p className="text-[10px] leading-snug text-muted-foreground" title={fill.reason}>
          {fill.reason}
        </p>
      ) : null}
      {editing ? (
        <form
          className="space-y-1.5 pt-1"
          onSubmit={(e) => {
            e.preventDefault();
            onSave(field.field_id);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.preventDefault();
              onCancel();
            }
          }}
        >
          <label htmlFor={`edit-${field.field_id}`} className="sr-only">
            Value for {field.label}
          </label>
          <input
            id={`edit-${field.field_id}`}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
            value={editValue}
            onChange={(e) => onEditChange(e.target.value)}
            autoFocus
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" className="h-7" disabled={busy === field.field_id}>
              {busy === field.field_id ? (
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
              ) : null}
              Save
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7"
              onClick={onCancel}
              disabled={busy != null}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : null}
    </li>
  );
}

// ─── Audit feed ────────────────────────────────────────────────────────────

const ACTION_COLOR: Record<string, string> = {
  fill: 'text-emerald-600 dark:text-emerald-400',
  checkpoint: 'text-amber-600 dark:text-amber-400',
  confirm_checkpoint: 'text-emerald-600 dark:text-emerald-400',
  open: 'text-sky-600 dark:text-sky-400',
  form: 'text-sky-600 dark:text-sky-400',
  guidance: 'text-violet-600 dark:text-violet-400',
  submit: 'text-rose-600 dark:text-rose-400',
  abort: 'text-red-600 dark:text-red-400',
};

function AuditFeed({ actions }: { actions: AuditAction[] }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Assistant audit feed</CardTitle>
        <CardDescription>Live actions, newest first (1s polling while active).</CardDescription>
      </CardHeader>
      <CardContent>
        {actions.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            No assistant actions yet.
          </p>
        ) : (
          <ScrollArea className="h-64">
            <ol role="log" aria-live="polite" className="space-y-1 pr-2">
              {actions.map((a) => (
                <li
                  key={a.id}
                  className="flex items-baseline gap-2 rounded px-1.5 py-1 text-[11px] odd:bg-muted/40"
                >
                  <time className="shrink-0 font-mono text-muted-foreground">
                    {new Date(a.occurred_at).toLocaleTimeString()}
                  </time>
                  <span className={cn('shrink-0 font-semibold', ACTION_COLOR[a.action] ?? '')}>
                    {a.action}
                  </span>
                  {a.field_id ? (
                    <span className="shrink-0 font-mono text-muted-foreground">{a.field_id}</span>
                  ) : null}
                  <span className="min-w-0 flex-1 truncate text-muted-foreground" title={a.audit_note ?? a.target ?? undefined}>
                    {a.audit_note ?? a.target}
                  </span>
                </li>
              ))}
            </ol>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Guidance (takeover) view ──────────────────────────────────────────────

function GuidanceCard({ plan }: { plan: GuidancePlan | null }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Eye className="h-4 w-4 text-amber-500" aria-hidden="true" />
          Human in control — guidance only
        </CardTitle>
        <CardDescription>
          You are driving the visible browser. The assistant annotates but
          never fights back (04 §7): no fields are written while you drive.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {plan ? (
          <>
            <p className="text-xs text-muted-foreground">{plan.reason}</p>
            {plan.steps.length === 0 ? (
              <p className="text-xs">No outstanding guidance — every known field is handled.</p>
            ) : (
              <ol className="space-y-2">
                {plan.steps.map((step) => (
                  <li key={step.field_id} className="rounded-md border border-border/60 px-2.5 py-2 text-xs">
                    <p className="font-medium">{step.label}</p>
                    <p className="mt-0.5 text-muted-foreground">{step.instruction}</p>
                  </li>
                ))}
              </ol>
            )}
          </>
        ) : (
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            Building guidance plan…
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Main panel ────────────────────────────────────────────────────────────

export default function Assistant() {
  const { sessionId = '' } = useParams<{ sessionId: string }>();
  const [terminal, setTerminal] = useState(false);
  // 1s session poll while active (07_UI §5); stops on terminal states.
  const sessionQuery = useSession(sessionId, !terminal);
  const session = sessionQuery.data?.session;

  const [state, setState] = useState<PanelState>(INITIAL_STATE);
  const stateRef = useRef(state);
  const advancedRef = useRef(false);
  const sessionRef = useRef(session);
  sessionRef.current = session;

  const update = useCallback((patch: Partial<PanelState>) => {
    stateRef.current = { ...stateRef.current, ...patch };
    setState(stateRef.current);
  }, []);

  useEffect(() => {
    if (session?.state === 'SUBMITTED' || session?.state === 'ABORTED') setTerminal(true);
  }, [session?.state]);

  // ── Error handling (409/403/503 envelope messages; takeover → guidance) ──
  const handleError = useCallback(
    async (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('taken over')) {
        // 409 "human has taken over the browser" → annotate-only (04 §7).
        update({ phase: 'guidance', browser: stateRef.current.browser ? { ...stateRef.current.browser, state: 'taken_over' } : null });
        try {
          update({ guidance: (await api.browserGuidance(sessionId)).data });
        } catch {
          /* guidance is best-effort; the actions feed keeps polling */
        }
        return;
      }
      if (msg.includes('no open browser session')) {
        update({ phase: 'idle', error: msg });
        return;
      }
      update({ error: msg, busy: null });
    },
    [sessionId, update],
  );

  // ── Open the browser session (fetch the session's opportunity first) ────
  const opportunityId = session?.opportunity_id ?? null;

  useEffect(() => {
    if (!sessionId || !opportunityId) return;
    // Already advanced / terminal sessions never re-open the browser.
    const st = sessionRef.current?.state;
    if (st === 'FORM_FILLED' || st === 'SUBMITTED' || st === 'ABORTED') {
      update({ phase: st === 'FORM_FILLED' ? 'done' : 'idle' });
      return;
    }
    if (stateRef.current.phase !== 'loading') return;
    let cancelled = false;
    (async () => {
      update({ phase: 'opening' });
      try {
        let form: FormModel;
        try {
          // Already-open browser for this session → just read the form.
          form = (await api.browserForm(sessionId)).data;
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          if (!msg.includes('no open browser session')) throw err;
          await api.browserOpen({ opportunity_id: opportunityId, session_id: sessionId });
          form = (await api.browserForm(sessionId)).data;
        }
        if (cancelled) return;
        update({
          form,
          browser: {
            session_id: sessionId,
            opportunity_id: opportunityId,
            url: '',
            state: 'opened',
            page_url: null,
            title: null,
          },
          phase: 'filling',
        });
        try {
          update({ actions: (await api.browserActions(sessionId, 100)).data });
        } catch {
          /* the 1s actions poll picks it up */
        }
      } catch (err) {
        if (cancelled) return;
        await handleError(err);
        // handleError may have switched to guidance (takeover during open);
        // only idle out if we are still mid-open.
        if (stateRef.current.phase === 'opening') update({ phase: 'idle' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, opportunityId, state.phase, update, handleError]);

  // ── FORM_FILLED advancement (only opened + auto_fillable + all gates clear) ──
  const maybeAdvance = useCallback(async () => {
    if (advancedRef.current) return;
    const s = stateRef.current;
    const st = sessionRef.current?.state;
    if (st === 'FORM_FILLED' || st === 'SUBMITTED' || st === 'ABORTED') {
      update({ phase: 'done' });
      return;
    }
    if (!s.form) return;
    if (!s.form.auto_fillable) {
      // Not auto-fillable → the session must never advance (frozen spec);
      // hold in checkpoint phase so the loops pause (the note + feed stay).
      update({ phase: 'checkpoint' });
      return;
    }
    if (s.browser?.state !== 'opened') return; // taken_over / aborted → never advance
    if (s.checkpoint) return; // gates remain
    const total = s.form.fields.length;
    const filled = s.form.fields.filter((f) => s.fills[f.field_id]?.filled).length;
    if (filled !== total) return;
    advancedRef.current = true;
    try {
      await api.advanceSession(sessionId, 'FORM_FILLED', {
        form_summary: { filled, total },
      });
      update({ phase: 'done', busy: null });
    } catch (err) {
      advancedRef.current = false;
      await handleError(err);
    }
  }, [sessionId, update, handleError]);

  // ── Driving tick: form → fill → checkpoint → advance ─────────────────────
  const driveTick = useCallback(async () => {
    const s = stateRef.current;
    if (s.phase !== 'filling') return;
    try {
      if (!s.form) {
        const form = (await api.browserForm(sessionId)).data;
        update({ form });
        return;
      }
      if (s.checkpoint) return; // a gate is open — waiting on the human
      const next = s.form.fields.find((f) => !(f.field_id in s.fills));
      if (next) {
        update({ busy: next.field_id });
        const fill = (await api.browserFill(next.field_id, sessionId)).data;
        update({
          fills: { ...stateRef.current.fills, [fill.field_id]: fill },
          busy: null,
        });
        return;
      }
      // Every field attempted → surface the next open §7 gate (or advance).
      const cp = (await api.browserCheckpoint(sessionId)).data;
      if (cp) update({ checkpoint: cp, phase: 'checkpoint' });
      else await maybeAdvance();
    } catch (err) {
      update({ busy: null });
      await handleError(err);
    }
  }, [sessionId, update, maybeAdvance, handleError]);

  const actionsTick = useCallback(async () => {
    const s = stateRef.current;
    if (s.phase === 'idle' || s.phase === 'loading' || s.phase === 'opening') return;
    try {
      const actions = (await api.browserActions(sessionId, 100)).data;
      update({ actions });
    } catch {
      /* transient feed errors are non-fatal */
    }
  }, [sessionId, update]);

  const driveRef = useRef(driveTick);
  const actionsRef = useRef(actionsTick);
  driveRef.current = driveTick;
  actionsRef.current = actionsTick;

  // 1s polling while the session is active (07_UI §5); stop on terminal states.
  useEffect(() => {
    if (!sessionId || terminal) return;
    if (state.phase === 'idle' || state.phase === 'loading' || state.phase === 'opening') return;
    const driving = state.phase === 'filling' ? window.setInterval(() => void driveRef.current(), 1000) : null;
    const actions = window.setInterval(() => void actionsRef.current(), 1000);
    return () => {
      if (driving != null) window.clearInterval(driving);
      window.clearInterval(actions);
    };
  }, [sessionId, terminal, state.phase]);

  // Session already advanced / terminal → collapse to the matching phase.
  useEffect(() => {
    if (!session) return;
    if (session.state === 'FORM_FILLED') update({ phase: 'done' });
    if (terminal) update({ phase: 'idle' });
  }, [session, terminal, update]);

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleConfirm = async () => {
    const s = stateRef.current;
    if (!s.checkpoint || s.busy) return;
    update({ busy: 'confirm' });
    try {
      const browser = (await api.browserConfirm(s.checkpoint.checkpoint_id, 'confirm', sessionId)).data;
      update({
        browser: browser,
        checkpoint: null,
        phase: 'filling', // tick re-evaluates the next gate / advances
        busy: null,
      });
    } catch (err) {
      update({ busy: null });
      await handleError(err);
    }
  };

  const handleTakeOver = async () => {
    update({ phase: 'guidance', checkpoint: null, error: null });
    try {
      update({ guidance: (await api.browserGuidance(sessionId)).data });
    } catch (err) {
      await handleError(err);
    }
  };

  const startEdit = (fieldId: string) => {
    const s = stateRef.current;
    const fill = s.fills[fieldId];
    const value = fill?.resolution?.typed_value == null ? '' : String(fill.resolution.typed_value);
    update({ editingFieldId: fieldId, editValue: value, error: null });
  };

  const cancelEdit = () => update({ editingFieldId: null, editValue: '' });

  const saveEdit = async (fieldId: string) => {
    const s = stateRef.current;
    const fill = s.fills[fieldId];
    const questionFp = fill?.resolution?.question_fp;
    if (typeof questionFp !== 'string') return;
    update({ busy: fieldId });
    try {
      // Confirm the edited value in the Answer Bank, then re-run the fill pass
      // for this field so the new value is written (or re-staged).
      await api.confirmAnswer({ question_fp: questionFp, answer: s.editValue });
      const refill = (await api.browserFill(fieldId, sessionId)).data;
      update({
        fills: { ...stateRef.current.fills, [fieldId]: refill },
        checkpoint: null,
        phase: 'filling', // gates may have cleared — let the tick re-check
        editingFieldId: null,
        editValue: '',
        busy: null,
      });
    } catch (err) {
      update({ busy: null });
      await handleError(err);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────

  if (!sessionId) {
    return (
      <div className="p-6">
        <ErrorBanner message="Missing session id in the route." />
      </div>
    );
  }

  const notAutoFillable =
    state.form != null &&
    !state.form.auto_fillable &&
    state.phase === 'checkpoint' &&
    state.checkpoint == null; // fill pass done, gates cleared — held, never advanced

  return (
    <div className="space-y-4 p-4 lg:p-6">
      <header className="flex flex-wrap items-center gap-2">
        <Bot className="h-5 w-5 text-primary" aria-hidden="true" />
        <h1 className="text-lg font-semibold tracking-tight">Form-Fill Assistant</h1>
        <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
          {sessionId}
        </code>
        {state.browser ? (
          <span className="ml-auto">
            <StateBadge state={state.phase === 'guidance' ? 'taken_over' : state.browser.state} />
          </span>
        ) : null}
      </header>

      {state.error ? (
        <ErrorBanner
          message={state.error}
          onDismiss={() => update({ error: null })}
          onRetry={
            state.phase === 'idle'
              ? () => {
                  advancedRef.current = false;
                  update({ ...INITIAL_STATE, phase: 'loading' });
                }
              : undefined
          }
        />
      ) : null}

      {sessionQuery.isError ? (
        <ErrorBanner
          message={sessionQuery.error instanceof Error ? sessionQuery.error.message : 'Session could not be loaded'}
          onRetry={() => void sessionQuery.refetch()}
        />
      ) : null}

      {terminal ? (
        <Card>
          <CardContent className="p-6 text-sm">
            {session?.state === 'SUBMITTED' ? (
              <p className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> Session submitted —
                the application workflow is complete.
              </p>
            ) : (
              <p className="flex items-center gap-2 text-red-600 dark:text-red-400">
                <AlertTriangle className="h-4 w-4" aria-hidden="true" /> Session aborted — no
                further assistant actions.
              </p>
            )}
          </CardContent>
        </Card>
      ) : null}

      {(state.phase === 'loading' || state.phase === 'opening') && !state.error && !sessionQuery.isError ? (
        <Card>
          <CardContent className="flex items-center justify-center gap-2 p-10 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {state.phase === 'opening' ? 'Opening the controlled browser…' : 'Loading session…'}
          </CardContent>
        </Card>
      ) : null}

      {state.phase !== 'loading' && state.phase !== 'opening' && !terminal ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="space-y-4">
            <StatusCard browser={state.browser} form={state.form} phase={state.phase} />

            {state.phase === 'guidance' ? (
              <GuidanceCard plan={state.guidance} />
            ) : state.checkpoint ? (
              <CheckpointBanner
                checkpoint={state.checkpoint}
                fields={state.form?.fields ?? []}
                busy={state.busy}
                onContinue={handleConfirm}
                onEdit={startEdit}
                onTakeOver={handleTakeOver}
              />
            ) : null}

            {notAutoFillable ? (
              <div
                role="status"
                className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-600 dark:text-amber-400"
              >
                This ATS form is not auto-fillable — the assistant cannot drive it.
                Fill the form manually in the visible browser, or use the guidance
                view.
              </div>
            ) : null}

            {state.phase === 'done' ? (
              <div
                role="status"
                className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-600 dark:text-emerald-400"
              >
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                Form filled and gates confirmed — the workspace wizard's submit
                step is unlocked.
              </div>
            ) : null}

            <AuditFeed actions={state.actions} />
          </div>

          <aside aria-label="Form fields">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  Form fields
                  <span className="ml-auto text-xs font-normal text-muted-foreground">
                    {state.form ? `${Object.keys(state.fills).length}/${state.form.fields.length} attempted` : '…'}
                  </span>
                </CardTitle>
                <CardDescription>
                  Fill status, confidence and value source per field.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {!state.form ? (
                  <p className="py-6 text-center text-xs text-muted-foreground">
                    Form model not loaded yet.
                  </p>
                ) : state.form.fields.length === 0 ? (
                  <p className="py-6 text-center text-xs text-muted-foreground">
                    No form fields detected on the page.
                  </p>
                ) : (
                  <ScrollArea className="h-[520px]">
                    <ul className="space-y-2 pr-2">
                      {state.form.fields.map((field) => (
                        <FieldRow
                          key={field.field_id}
                          field={field}
                          fill={state.fills[field.field_id]}
                          editing={state.editingFieldId === field.field_id}
                          editValue={state.editValue}
                          busy={state.busy}
                          onEdit={startEdit}
                          onEditChange={(v) => update({ editValue: v })}
                          onSave={saveEdit}
                          onCancel={cancelEdit}
                        />
                      ))}
                    </ul>
                  </ScrollArea>
                )}
              </CardContent>
            </Card>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
