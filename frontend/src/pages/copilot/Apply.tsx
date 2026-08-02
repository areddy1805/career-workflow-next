import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  Check,
  CheckCircle2,
  ExternalLink,
  FileText,
  Loader2,
  Lock,
  Pencil,
  Send,
  Sparkles,
} from 'lucide-react';
import { useBrief, useCopilotOpportunity, useSession } from '@/lib/hooks';
import * as api from '@/lib/api/copilot';
import {
  WORKSPACE_STEPS,
  useCopilotStore,
  type WorkspaceStep,
} from '@/store/copilot';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/button';
import { cn, formatSalary } from '@/lib/utils';
import type { CopilotSession, SessionEvent, StoredAnswer } from '@/lib/types/copilot';

/**
 * Application Workspace wizard (docs/application_copilot/07_UI.md §3.2, CP-6-03).
 *
 * Five steps (brief → answers → resume → assistant → submit) driven by the
 * session state machine (02_ARCHITECTURE.md §7.5): BRIEF_READY → step brief,
 * ANSWERS_REVIEWED → answers, RESUME_SELECTED → resume, FORM_FILLED →
 * assistant, SUBMITTED → submit/outcome. The rail allows viewing any step;
 * actions are gated on the backend-valid transition (e.g. RESUME_CHOSEN only
 * fires while ANSWERS_REVIEWED, so the resume step is actionable one state
 * ahead of its display slot).
 *
 * The submit button requires a deliberate hold-to-confirm gesture (ADR-002):
 * the backend rejects HUMAN_SUBMIT without human_gesture=true, and the UI
 * enforces the ~1s press-and-hold on top (button is inert without it).
 */

// ─── Frozen mapping (backend state_machine.py) ─────────────────────────────

const STATE_TO_STEP: Record<string, number> = {
  BRIEF_READY: 0,
  ANSWERS_REVIEWED: 1,
  RESUME_SELECTED: 2,
  FORM_FILLED: 3,
  SUBMITTED: 4,
  ABORTED: 0,
};

const STEP_META: Record<WorkspaceStep, { label: string; hint: string }> = {
  brief: { label: 'Brief', hint: 'Job summary & verdict' },
  answers: { label: 'Answers', hint: 'Screening answers' },
  resume: { label: 'Resume', hint: 'Choose resume' },
  assistant: { label: 'Assistant', hint: 'Form-fill assistant' },
  submit: { label: 'Submit', hint: 'Final review & submit' },
};

const HOLD_MS = 1000;

// ─── Snapshot shapes (session.answers_snapshot_json / brief_snapshot_json) ─

interface AnswerSnapshotEntry {
  question: string;
  question_fp: string;
  source: string;
  semantic_answer: unknown;
  serialized_answer: unknown;
  confidence: number | null;
  status: string;
  reasoning: string | null;
}

interface BriefSnapshot {
  verdict?: string | null;
  verdict_reason?: string | null;
  fit?: { score?: number; fit_class?: string | null } | null;
  strategy?: { strategy?: string; reason?: string } | null;
  salary?: { status?: string; reason?: string } | null;
  effort?: { estimated_minutes?: number | null } | null;
  interview_probability?: number | null;
  resume_recommendation?: {
    resume_type?: string | null;
    reason?: string | null;
    scores?: Record<string, number> | null;
    path?: string | null;
  } | null;
  questions?: { question?: string; answer?: string }[] | null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Raw POST to a copilot endpoint; surfaces the {ok,error} envelope message.
 *  ponytail: fetchApi (base.ts) drops the nested `error.message` for non-2xx,
 *  so this local helper re-reads the envelope to show real backend errors. */
async function postCopilot<T>(endpoint: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(`/api${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = (await res.json().catch(() => null)) as
    | { ok?: boolean; data?: T; error?: { message?: string }; message?: string }
    | null;
  if (!res.ok || !data?.ok) {
    throw new Error(data?.error?.message || data?.message || res.statusText);
  }
  return data.data as T;
}

function toMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Request failed';
}

function parseSnapshot(raw: string | null): AnswerSnapshotEntry[] | null {
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as AnswerSnapshotEntry[]) : null;
  } catch {
    return null;
  }
}

function parseBriefSnapshot(raw: string | null): BriefSnapshot | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as BriefSnapshot;
  } catch {
    return null;
  }
}

function stringifyAnswer(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

// ─── Small pieces ───────────────────────────────────────────────────────────

const ANSWER_STATUS_STYLES: Record<string, string> = {
  auto: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  confirmed: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  confirm: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  manual: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  manual_review: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  locked: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  superseded: 'bg-muted text-muted-foreground',
};

function AnswerStatusChip({ status }: { status: string }) {
  const upper = (status || 'unknown').toUpperCase();
  return (
    <span
      className={cn(
        'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold font-mono uppercase tracking-wide leading-none whitespace-nowrap',
        ANSWER_STATUS_STYLES[status] ?? 'bg-zinc-500/8 text-zinc-500',
      )}
    >
      {upper}
    </span>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-600 dark:text-red-400"
    >
      <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" aria-hidden="true" />
      <span className="min-w-0 break-words">{message}</span>
    </div>
  );
}

function ReadOnlyNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-xs text-muted-foreground">
      <Lock className="w-3 h-3 shrink-0" aria-hidden="true" />
      {children}
    </p>
  );
}

/** Deliberate-gesture submit button (ADR-002): inert until pressed-and-held
 *  ~1s; release fires, early release/leave cancels. Keyboard: hold Space/Enter. */
function HoldToConfirmButton({
  disabled,
  busy,
  onConfirm,
  describedBy,
}: {
  disabled: boolean;
  busy: boolean;
  onConfirm: () => void;
  describedBy?: string;
}) {
  const [holding, setHolding] = useState(false);
  const [armed, setArmed] = useState(false);
  const timer = useRef<number | null>(null);
  const armedRef = useRef(false);
  const firedRef = useRef(false);

  const clearHold = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    armedRef.current = false;
    setArmed(false);
    setHolding(false);
  }, []);

  const startHold = useCallback(() => {
    if (disabled || busy) return;
    if (timer.current !== null) window.clearTimeout(timer.current);
    firedRef.current = false;
    setHolding(true);
    timer.current = window.setTimeout(() => {
      timer.current = null;
      armedRef.current = true;
      setArmed(true);
    }, HOLD_MS);
  }, [disabled, busy]);

  const endHold = useCallback(() => {
    const wasArmed = armedRef.current;
    clearHold();
    if (wasArmed && !firedRef.current) {
      firedRef.current = true;
      onConfirm();
    }
  }, [clearHold, onConfirm]);

  useEffect(() => {
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, []);

  const inert = disabled || busy;

  return (
    <div className="space-y-1.5">
      <button
        type="button"
        disabled={inert}
        aria-describedby={describedBy}
        onPointerDown={startHold}
        onPointerUp={endHold}
        onPointerLeave={clearHold}
        onPointerCancel={clearHold}
        onKeyDown={(e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault();
            startHold();
          }
        }}
        onKeyUp={(e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault();
            endHold();
          }
        }}
        onClick={(e) => {
          // Inert without the hold: plain clicks never fire the submit.
          e.preventDefault();
        }}
        className={cn(
          'relative overflow-hidden rounded-md px-6 py-3 text-sm font-semibold transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'disabled:opacity-50 disabled:pointer-events-none',
          armed
            ? 'bg-emerald-600 text-white hover:bg-emerald-600'
            : 'bg-primary text-primary-foreground hover:bg-primary/90',
        )}
      >
        <span className="relative z-10 flex items-center justify-center gap-2">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> : null}
          {holding ? (armed ? 'Release to submit' : 'Keep holding…') : 'Submit application'}
        </span>
        {/* progress fill mirrors the hold duration */}
        <span
          aria-hidden="true"
          className={cn(
            'absolute inset-y-0 left-0 bg-white/25',
            holding ? 'opacity-100' : 'opacity-0',
          )}
          style={{
            width: holding ? '100%' : '0%',
            transition: holding ? `width ${HOLD_MS}ms linear` : 'none',
          }}
        />
      </button>
      <p id={describedBy} className="text-[11px] text-muted-foreground">
        Press and hold ~1 second to enable — releasing early cancels. Keyboard: hold Space or Enter.
      </p>
    </div>
  );
}

// ─── Wizard ─────────────────────────────────────────────────────────────────

export default function Apply() {
  const { id } = useParams<{ id: string }>();
  const opportunityId = id ?? '';
  const queryClient = useQueryClient();

  const { opportunityId: boundOpp, sessionId, step, setStep, setSession } = useCopilotStore();
  const { data: opportunity } = useCopilotOpportunity(opportunityId);
  const briefQuery = useBrief(opportunityId);

  const [createAttempt, setCreateAttempt] = useState(0);
  const [createError, setCreateError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  // ── Session creation (mount): bind the wizard to one session per opportunity ──
  useEffect(() => {
    if (!opportunityId) return;
    if (boundOpp === opportunityId && sessionId) return;
    let cancelled = false;
    setCreateError(null);
    api
      .createSession({ opportunity_id: opportunityId })
      .then((res) => {
        if (!cancelled && res.ok) setSession(opportunityId, res.data.session_id);
      })
      .catch((err: unknown) => {
        if (!cancelled) setCreateError(toMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [opportunityId, boundOpp, sessionId, setSession, createAttempt]);

  // ── Session fetch + 1s poll while the wizard is active (07_UI §5) ──
  // The poll flag depends on the session itself, so it lives in a ref that an
  // effect updates once data lands (breaks the hook-call circularity).
  const pollActiveRef = useRef(true);
  const sessionQuery = useSession(sessionId ?? '', pollActiveRef.current);
  const sessionDetail = sessionQuery.data;
  const session = sessionDetail?.session ?? null;
  const state = session?.state ?? null;
  const terminal = state === 'SUBMITTED' || state === 'ABORTED';
  useEffect(() => {
    if (!session) return;
    // Keep polling until the run is terminal AND the outcome is recorded.
    pollActiveRef.current = !terminal || !session.outcome;
  }, [session, terminal]);

  // ── Drive the view step from the session state (auto-advance only forward) ──
  const sessionStepIndex = state ? (STATE_TO_STEP[state] ?? 0) : 0;
  const lastSeenStep = useRef(-1);
  useEffect(() => {
    if (!session) return;
    if (sessionStepIndex > lastSeenStep.current) {
      lastSeenStep.current = sessionStepIndex;
      setStep(WORKSPACE_STEPS[sessionStepIndex]);
    }
  }, [session, sessionStepIndex, setStep]);

  const stepIndex = WORKSPACE_STEPS.indexOf(step);

  /** Actions are gated on the backend-valid transition from the current state:
   *  RESUME_CHOSEN fires from ANSWERS_REVIEWED, FORM_FILLED from RESUME_SELECTED,
   *  HUMAN_SUBMIT from FORM_FILLED (state_machine.py). */
  const canAct = useCallback(
    (s: WorkspaceStep): boolean => {
      switch (s) {
        case 'brief':
          return state === 'BRIEF_READY';
        case 'answers':
          return state === 'ANSWERS_REVIEWED';
        case 'resume':
          return state === 'ANSWERS_REVIEWED';
        case 'assistant':
          return state === 'RESUME_SELECTED';
        case 'submit':
          return state === 'FORM_FILLED';
      }
    },
    [state],
  );

  const refreshSession = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['copilot', 'session', sessionId] });
  }, [queryClient, sessionId]);

  // ── Actions (advance events, §7.5) ──
  const begin = useCallback(async () => {
    if (!sessionId || busy) return;
    setBusy('begin');
    setActionError(null);
    try {
      await postCopilot<CopilotSession>(`/copilot/sessions/${sessionId}/advance`, {
        event: 'ANSWERS_CONFIRMED',
        payload: {},
      });
      refreshSession();
    } catch (err) {
      setActionError(toMessage(err));
    } finally {
      setBusy(null);
    }
  }, [sessionId, busy, refreshSession]);

  const chooseResume = useCallback(
    async (resumeId: string) => {
      if (!sessionId || busy) return;
      setBusy('resume');
      setActionError(null);
      try {
        await postCopilot<CopilotSession>(`/copilot/sessions/${sessionId}/advance`, {
          event: 'RESUME_CHOSEN',
          payload: { resume_id: resumeId },
        });
        refreshSession();
      } catch (err) {
        setActionError(toMessage(err));
      } finally {
        setBusy(null);
      }
    },
    [sessionId, busy, refreshSession],
  );

  const submit = useCallback(async () => {
    if (!sessionId || busy) return;
    setBusy('submit');
    setActionError(null);
    try {
      await postCopilot<CopilotSession>(`/copilot/sessions/${sessionId}/advance`, {
        event: 'HUMAN_SUBMIT',
        payload: { human_gesture: true },
      });
      refreshSession();
    } catch (err) {
      setActionError(toMessage(err));
    } finally {
      setBusy(null);
    }
  }, [sessionId, busy, refreshSession]);

  // ── Answers view state (snapshot + local patches survive poll refetches) ──
  const briefSnap = useMemo(
    () => parseBriefSnapshot(session?.brief_snapshot_json ?? null),
    [session],
  );
  const snapshot = useMemo(
    () => parseSnapshot(session?.answers_snapshot_json ?? null),
    [session],
  );
  const [patches, setPatches] = useState<Record<string, AnswerSnapshotEntry>>({});
  const entries = useMemo(
    () => (snapshot ?? []).map((e) => patches[e.question_fp] ?? e),
    [snapshot, patches],
  );
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState('');
  const [focusedSlot, setFocusedSlot] = useState<number | null>(null);
  const answerRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const patchEntry = useCallback((fp: string, entry: AnswerSnapshotEntry) => {
    setPatches((prev) => ({ ...prev, [fp]: entry }));
  }, []);

  const startEdit = useCallback(
    (idx: number) => {
      const entry = entries[idx];
      if (!entry || !canAct('answers')) return;
      setEditingIndex(idx);
      setDraft(stringifyAnswer(entry.semantic_answer));
    },
    [entries, canAct],
  );

  const cancelEdit = useCallback(() => {
    setEditingIndex(null);
  }, []);

  useEffect(() => {
    if (editingIndex !== null) textareaRef.current?.focus();
  }, [editingIndex]);

  const saveEdit = useCallback(async () => {
    const idx = editingIndex;
    const entry = idx !== null ? entries[idx] : null;
    if (!entry || !session || busy) return;
    setBusy('edit');
    setActionError(null);
    try {
      const saved = await postCopilot<StoredAnswer>('/copilot/answers/confirm', {
        question_fp: entry.question_fp,
        profile_id: session.profile_id ?? 'generic',
        answer: draft,
        actor: 'user',
      });
      patchEntry(entry.question_fp, {
        question: entry.question,
        question_fp: entry.question_fp,
        source: saved.source,
        semantic_answer: saved.semantic_answer,
        serialized_answer: saved.serialized_answer,
        confidence: saved.confidence,
        status: saved.status,
        reasoning: saved.reason ?? entry.reasoning,
      });
      cancelEdit();
    } catch (err) {
      setActionError(toMessage(err));
    } finally {
      setBusy(null);
    }
  }, [editingIndex, entries, session, busy, draft, patchEntry, cancelEdit]);

  /** Bulk confirm (07_UI §3.2 step 2): POST confirm per answer. Locked rows are
   *  skipped — the backend rejects confirm on locked answers (confirm.py). */
  const confirmAll = useCallback(async () => {
    if (!entries.length || !session || busy) return;
    setBusy('confirmAll');
    setActionError(null);
    const results = await Promise.allSettled(
      entries
        .filter((e) => e.status !== 'locked')
        .map((e) =>
          postCopilot<StoredAnswer>('/copilot/answers/confirm', {
            question_fp: e.question_fp,
            profile_id: session.profile_id ?? 'generic',
            answer: e.semantic_answer,
            actor: 'user',
          }),
        ),
    );
    let failed = 0;
    let i = 0;
    entries.forEach((entry) => {
      if (entry.status === 'locked') return;
      const r = results[i++];
      if (r.status === 'fulfilled') {
        const saved = r.value;
        patchEntry(entry.question_fp, {
          ...entry,
          source: saved.source,
          semantic_answer: saved.semantic_answer,
          serialized_answer: saved.serialized_answer,
          confidence: saved.confidence,
          status: saved.status,
          reasoning: saved.reason ?? entry.reasoning,
        });
      } else {
        failed += 1;
      }
    });
    if (failed > 0) {
      setActionError(`${failed} answer${failed > 1 ? 's' : ''} could not be confirmed — see answer status.`);
    }
    setBusy(null);
  }, [entries, session, busy, patchEntry]);

  // ── Resume selection state ──
  const rec = briefSnap?.resume_recommendation ?? null;
  const resumeCandidates = useMemo(() => {
    const types = ['AI', 'FDE'];
    if (rec?.resume_type && !types.includes(rec.resume_type)) types.push(rec.resume_type);
    return types;
  }, [rec]);
  const [selectedResume, setSelectedResume] = useState<string | null>(null);
  useEffect(() => {
    if (rec?.resume_type) setSelectedResume(rec.resume_type);
    if (session?.resume_id) setSelectedResume(session.resume_id);
  }, [rec?.resume_type, session?.resume_id]);

  // ── Keyboard map (§3.2): enter advance, space confirm, 1-9 jump, e edit, esc back ──
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      if (target.closest('input, textarea, select')) return;

      if (step === 'answers') {
        if (e.key >= '1' && e.key <= '9') {
          const idx = Number(e.key) - 1;
          if (idx < entries.length) {
            e.preventDefault();
            answerRefs.current[idx]?.focus();
          }
          return;
        }
        if (e.key === 'e') {
          if (focusedSlot !== null && focusedSlot < entries.length && editingIndex === null) {
            e.preventDefault();
            startEdit(focusedSlot);
          }
          return;
        }
        if (e.key === ' ' && canAct('answers')) {
          if (target.closest('button, a')) return; // let focused controls act
          e.preventDefault();
          void confirmAll();
          return;
        }
      }

      if (e.key === 'Enter') {
        if (target.closest('button, a')) return; // let focused controls act
        e.preventDefault();
        if (step === 'brief' && canAct('brief')) void begin();
        else if (step === 'answers' && canAct('answers')) void confirmAll();
        else if (step === 'resume' && canAct('resume')) {
          if (selectedResume) void chooseResume(selectedResume);
        }
      } else if (e.key === 'Escape') {
        if (editingIndex !== null) cancelEdit();
        else if (stepIndex > 0) setStep(WORKSPACE_STEPS[stepIndex - 1]);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [
    step,
    stepIndex,
    entries,
    focusedSlot,
    editingIndex,
    selectedResume,
    canAct,
    begin,
    confirmAll,
    chooseResume,
    cancelEdit,
    startEdit,
    setStep,
  ]);

  // ── Render ──
  if (!opportunityId) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
        Missing opportunity id.
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background text-sm animate-in fade-in duration-300">
      <header className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            to="/copilot/inbox"
            aria-label="Back to inbox"
            className="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          </Link>
          <div className="min-w-0">
            <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
              <Send className="w-4 h-4 text-primary" aria-hidden="true" />
              Application Workspace
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5 truncate">
              {opportunity
                ? `${opportunity.title} · ${opportunity.company}`
                : 'Loading opportunity…'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {session ? <StatusBadge status={state ?? ''} /> : null}
          {sessionId ? (
            <span className="text-[10px] font-mono text-muted-foreground">
              #{sessionId.slice(0, 8)}
            </span>
          ) : null}
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Progress rail (§3.2) */}
        <nav
          aria-label="Workspace steps"
          className="w-48 shrink-0 border-r border-border/50 bg-card/30 p-3 space-y-1 overflow-y-auto"
        >
          {WORKSPACE_STEPS.map((s, i) => {
            const active = s === step;
            const done = i < sessionStepIndex;
            const readOnly = !canAct(s);
            return (
              <button
                key={s}
                type="button"
                onClick={() => setStep(s)}
                aria-current={active ? 'step' : undefined}
                title={readOnly && !active ? `Locked — ${STEP_META[s].hint}` : STEP_META[s].hint}
                className={cn(
                  'w-full flex items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-xs transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  active
                    ? 'bg-primary/10 text-foreground font-semibold'
                    : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground',
                  readOnly && !active && 'opacity-60',
                )}
              >
                <span
                  className={cn(
                    'w-5 h-5 rounded-full border flex items-center justify-center text-[10px] font-semibold shrink-0',
                    done
                      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                      : active
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border',
                  )}
                >
                  {done ? <Check className="w-3 h-3" aria-hidden="true" /> : i + 1}
                </span>
                <span className="flex-1 truncate">{STEP_META[s].label}</span>
                {readOnly && !active ? (
                  <Lock className="w-3 h-3 opacity-50" aria-hidden="true" />
                ) : null}
              </button>
            );
          })}
        </nav>

        {/* Step content */}
        <main className="flex-1 overflow-y-auto p-6">
          {createError ? (
            <div className="max-w-xl mx-auto mt-16 bg-card border border-border/50 rounded-xl p-6 space-y-4 text-center">
              <AlertTriangle className="w-8 h-8 text-red-500 mx-auto" aria-hidden="true" />
              <p className="text-sm font-medium">Could not start a workspace session</p>
              <p className="text-xs text-muted-foreground">{createError}</p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setCreateAttempt((n) => n + 1)}
              >
                Retry
              </Button>
            </div>
          ) : !sessionId ? (
            <div className="h-full flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              Starting session…
            </div>
          ) : sessionQuery.isLoading || !session ? (
            <div className="h-full flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              Loading session…
            </div>
          ) : sessionQuery.isError ? (
            <div className="max-w-xl mx-auto mt-16 bg-card border border-border/50 rounded-xl p-6 space-y-4 text-center">
              <AlertTriangle className="w-8 h-8 text-red-500 mx-auto" aria-hidden="true" />
              <p className="text-sm font-medium">Could not load the session</p>
              <p className="text-xs text-muted-foreground">
                {sessionQuery.error instanceof Error ? sessionQuery.error.message : 'Unknown error'}
              </p>
              <Button size="sm" variant="outline" onClick={() => void sessionQuery.refetch()}>
                Retry
              </Button>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4" id="wizard-content">
              {actionError ? <ErrorBanner message={actionError} /> : null}
              {state === 'ABORTED' ? (
                <div
                  role="status"
                  className="flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-600 dark:text-amber-400"
                >
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                  This session was aborted. Start a new session from the inbox to apply again.
                </div>
              ) : null}

              {step === 'brief' ? (
                <BriefStep
                  briefQuery={briefQuery}
                  briefSnap={briefSnap}
                  opportunity={opportunity}
                  canBegin={canAct('brief')}
                  busy={busy === 'begin'}
                  onBegin={() => void begin()}
                />
              ) : step === 'answers' ? (
                <AnswersStep
                  entries={entries}
                  briefQuestions={briefSnap?.questions ?? null}
                  canEdit={canAct('answers')}
                  busy={busy}
                  editingIndex={editingIndex}
                  draft={draft}
                  onDraftChange={setDraft}
                  onStartEdit={startEdit}
                  onCancelEdit={cancelEdit}
                  onSaveEdit={() => void saveEdit()}
                  onConfirmAll={() => void confirmAll()}
                  onFocusSlot={setFocusedSlot}
                  registerSlotRef={(i, el) => {
                    answerRefs.current[i] = el;
                  }}
                  textareaRef={textareaRef}
                />
              ) : step === 'resume' ? (
                <ResumeStep
                  rec={rec}
                  candidates={resumeCandidates}
                  selected={selectedResume}
                  onSelect={setSelectedResume}
                  chosen={state === 'RESUME_SELECTED' ? (session.resume_id ?? null) : null}
                  canChoose={canAct('resume')}
                  busy={busy === 'resume'}
                  onChoose={() => {
                    if (selectedResume) void chooseResume(selectedResume);
                  }}
                />
              ) : step === 'assistant' ? (
                <AssistantStep
                  sessionId={sessionId}
                  canOpen={canAct('assistant')}
                  formFilled={state === 'FORM_FILLED'}
                />
              ) : (
                <SubmitStep
                  session={session}
                  events={sessionDetail?.events ?? []}
                  answersCount={entries.length}
                  opportunity={opportunity}
                  canSubmit={canAct('submit')}
                  busy={busy === 'submit'}
                  onSubmit={() => void submit()}
                />
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// ─── Step 1: Brief ──────────────────────────────────────────────────────────

function BriefStep({
  briefQuery,
  briefSnap,
  opportunity,
  canBegin,
  busy,
  onBegin,
}: {
  briefQuery: ReturnType<typeof useBrief>;
  briefSnap: BriefSnapshot | null;
  opportunity: ReturnType<typeof useCopilotOpportunity>['data'];
  canBegin: boolean;
  busy: boolean;
  onBegin: () => void;
}) {
  const verdict = briefSnap?.verdict ?? briefQuery.data?.verdict?.label ?? null;
  const sections = briefQuery.data?.sections ?? null;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight flex items-center gap-2">
          <FileText className="w-4 h-4 text-primary" aria-hidden="true" /> Job Brief
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Read-only summary of the opportunity and the recommended application plan.
        </p>
      </div>

      {verdict ? (
        <div
          role="status"
          className={cn(
            'flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium',
            verdict === 'apply'
              ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400'
              : verdict === 'skip'
                ? 'border-red-500/30 bg-red-500/5 text-red-600 dark:text-red-400'
                : 'border-amber-500/30 bg-amber-500/5 text-amber-600 dark:text-amber-400',
          )}
        >
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
          Verdict: <span className="font-semibold uppercase">{verdict}</span>
          {briefSnap?.verdict_reason ? ` — ${briefSnap.verdict_reason}` : null}
        </div>
      ) : null}

      {/* At a glance */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <GlanceStat
          label="Fit"
          value={
            briefSnap?.fit?.score != null
              ? `${Math.round(briefSnap.fit.score * 100)}%`
              : '—'
          }
        />
        <GlanceStat
          label="Strategy"
          value={briefSnap?.strategy?.strategy ?? '—'}
        />
        <GlanceStat
          label="Salary"
          value={
            opportunity
              ? formatSalary(opportunity.comp_min ?? undefined, opportunity.comp_max ?? undefined, opportunity.currency ?? undefined)
              : '—'
          }
        />
        <GlanceStat
          label="Interview odds"
          value={
            briefSnap?.interview_probability != null
              ? `${Math.round(briefSnap.interview_probability * 100)}%`
              : '—'
          }
        />
      </div>

      {briefQuery.isLoading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-8 justify-center">
          <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
          Loading brief…
        </div>
      ) : briefQuery.isError ? (
        <div className="bg-card border border-border/50 rounded-xl p-4 space-y-2">
          <p className="text-xs text-muted-foreground">
            Brief could not be loaded: {briefQuery.error instanceof Error ? briefQuery.error.message : 'unknown error'}
          </p>
          <Button size="sm" variant="outline" onClick={() => void briefQuery.refetch()}>
            Retry
          </Button>
        </div>
      ) : sections && sections.length > 0 ? (
        <div className="space-y-3">
          {sections.map((section) => (
            <div
              key={section.key}
              className="bg-card border border-border/50 rounded-xl p-4 space-y-1.5"
            >
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground">
                  {section.title}
                </h3>
                {section.llm_augmented ? (
                  <Sparkles
                    className="w-3 h-3 text-primary"
                    aria-label="LLM-augmented"
                  />
                ) : null}
              </div>
              <p className="text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed">
                {section.content}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground py-8 text-center">
          No brief sections available for this opportunity.
        </p>
      )}

      {/* CTA */}
      {canBegin ? (
        <div className="flex items-center gap-3 pt-2">
          <Button onClick={onBegin} disabled={busy} className="min-w-40">
            {busy ? (
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
            ) : (
              <Send className="w-4 h-4" aria-hidden="true" />
            )}
            Begin
          </Button>
          <span className="text-[11px] text-muted-foreground">
            Resolves screening answers from your Answer Bank. Press Enter to begin.
          </span>
        </div>
      ) : (
        <ReadOnlyNote>Session already started — screening answers were confirmed.</ReadOnlyNote>
      )}
    </div>
  );
}

function GlanceStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-card border border-border/50 rounded-lg px-3 py-2">
      <p className="text-[9px] text-muted-foreground uppercase tracking-widest font-semibold mb-0.5">
        {label}
      </p>
      <p className="font-mono text-[13px] font-semibold text-foreground truncate">{value}</p>
    </div>
  );
}

// ─── Step 2: Answers ────────────────────────────────────────────────────────

function AnswersStep({
  entries,
  briefQuestions,
  canEdit,
  busy,
  editingIndex,
  draft,
  onDraftChange,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onConfirmAll,
  onFocusSlot,
  registerSlotRef,
  textareaRef,
}: {
  entries: AnswerSnapshotEntry[];
  briefQuestions: BriefSnapshot['questions'] | null;
  canEdit: boolean;
  busy: string | null;
  editingIndex: number | null;
  draft: string;
  onDraftChange: (v: string) => void;
  onStartEdit: (idx: number) => void;
  onCancelEdit: () => void;
  onSaveEdit: () => void;
  onConfirmAll: () => void;
  onFocusSlot: (idx: number) => void;
  registerSlotRef: (idx: number, el: HTMLButtonElement | null) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}) {
  const lockedCount = entries.filter((e) => e.status === 'locked').length;

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold tracking-tight">Screening Answers</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {entries.length > 0
              ? `${entries.length} answer${entries.length > 1 ? 's' : ''} resolved from the Answer Bank. Keys 1-9 jump to a slot, E edits the focused slot.`
              : 'No resolved answers yet.'}
          </p>
        </div>
        {canEdit && entries.length > 0 ? (
          <Button
            size="sm"
            variant="secondary"
            onClick={onConfirmAll}
            disabled={busy !== null}
            title="Confirm every answer (Space)"
          >
            {busy === 'confirmAll' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <Check className="w-3.5 h-3.5" aria-hidden="true" />
            )}
            Confirm all
            {lockedCount > 0 ? ` (${lockedCount} locked)` : ''}
          </Button>
        ) : null}
      </div>

      {entries.length > 0 ? (
        <ul className="space-y-2" role="list">
          {entries.map((entry, i) => {
            const slot = i + 1;
            const isEditing = editingIndex === i;
            return (
              <li
                key={entry.question_fp}
                className={cn(
                  'bg-card border border-border/50 rounded-xl p-4 flex gap-3',
                  isEditing && 'ring-2 ring-ring',
                )}
              >
                <span
                  className="w-6 h-6 rounded-md border border-border flex items-center justify-center text-[10px] font-mono font-semibold text-muted-foreground shrink-0 mt-0.5"
                  aria-hidden="true"
                >
                  {slot}
                </span>
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-xs font-semibold text-foreground">{entry.question}</p>
                    <AnswerStatusChip status={entry.status} />
                  </div>
                  {isEditing ? (
                    <div className="space-y-2">
                      <textarea
                        ref={textareaRef}
                        value={draft}
                        onChange={(e) => onDraftChange(e.target.value)}
                        rows={4}
                        aria-label={`Edit answer for ${entry.question}`}
                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            onSaveEdit();
                          } else if (e.key === 'Escape') {
                            e.preventDefault();
                            onCancelEdit();
                          }
                        }}
                      />
                      <div className="flex items-center gap-2">
                        <Button size="sm" onClick={onSaveEdit} disabled={busy !== null}>
                          {busy === 'edit' ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                          ) : (
                            <Check className="w-3.5 h-3.5" aria-hidden="true" />
                          )}
                          Save answer
                        </Button>
                        <Button size="sm" variant="ghost" onClick={onCancelEdit}>
                          Cancel
                        </Button>
                        <span className="text-[11px] text-muted-foreground">
                          Enter saves, Shift+Enter newline, Esc cancels
                        </span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed">
                      {stringifyAnswer(entry.semantic_answer)}
                    </p>
                  )}
                  {entry.reasoning ? (
                    <p className="text-[11px] text-muted-foreground/70">{entry.reasoning}</p>
                  ) : null}
                </div>
                {canEdit && !isEditing ? (
                  <button
                    type="button"
                    ref={(el) => registerSlotRef(i, el)}
                    onFocus={() => onFocusSlot(i)}
                    onClick={() => onStartEdit(i)}
                    aria-label={`Edit answer ${slot}: ${entry.question}`}
                    className="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring shrink-0 self-start"
                  >
                    <Pencil className="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : briefQuestions && briefQuestions.length > 0 ? (
        <div className="bg-card border border-border/50 rounded-xl p-4 space-y-3">
          <p className="text-xs text-muted-foreground">
            Answers are resolved when the wizard begins. Likely screening questions from the brief:
          </p>
          <ul className="space-y-2" role="list">
            {briefQuestions.map((q, i) => (
              <li key={`${q.question}-${i}`} className="flex gap-3">
                <span className="w-6 h-6 rounded-md border border-border flex items-center justify-center text-[10px] font-mono font-semibold text-muted-foreground shrink-0">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-foreground">{q.question}</p>
                  {q.answer ? (
                    <p className="text-xs text-muted-foreground font-mono mt-0.5">{q.answer}</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="bg-card border border-dashed border-border/60 rounded-xl p-8 text-center space-y-1">
          <p className="text-sm font-medium">No screening answers</p>
          <p className="text-xs text-muted-foreground">
            No likely questions were detected for this opportunity.
          </p>
        </div>
      )}

      {!canEdit ? (
        <ReadOnlyNote>Editing unlocks after the wizard resolves the answers (Begin).</ReadOnlyNote>
      ) : null}
    </div>
  );
}

// ─── Step 3: Resume ─────────────────────────────────────────────────────────

function ResumeStep({
  rec,
  candidates,
  selected,
  onSelect,
  chosen,
  canChoose,
  busy,
  onChoose,
}: {
  rec: BriefSnapshot['resume_recommendation'];
  candidates: string[];
  selected: string | null;
  onSelect: (t: string) => void;
  chosen: string | null;
  canChoose: boolean;
  busy: boolean;
  onChoose: () => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight">Resume</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Pick the resume variant the application will be filed with.
        </p>
      </div>

      {rec ? (
        <div className="bg-card border border-primary/20 rounded-xl p-4 space-y-1.5">
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-primary" aria-hidden="true" />
            <h3 className="text-xs font-semibold uppercase tracking-wider">
              Recommended: {rec.resume_type}
            </h3>
          </div>
          {rec.reason ? (
            <p className="text-xs text-muted-foreground leading-relaxed">{rec.reason}</p>
          ) : null}
          {rec.scores && Object.keys(rec.scores).length > 0 ? (
            <div className="flex gap-4 pt-1">
              {Object.entries(rec.scores).map(([k, v]) => (
                <span key={k} className="text-[11px] font-mono text-muted-foreground">
                  {k}: <span className="text-foreground">{v}</span>
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          No resume recommendation in the brief — pick a variant below.
        </p>
      )}

      <div role="radiogroup" aria-label="Resume variant" className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {candidates.map((t) => {
          const isSelected = selected === t;
          const isRecommended = rec?.resume_type === t;
          return (
            <button
              key={t}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => onSelect(t)}
              className={cn(
                'rounded-xl border bg-card p-4 text-left transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isSelected
                  ? 'border-primary ring-1 ring-primary'
                  : 'border-border hover:border-border/70 hover:bg-muted/30',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold">{t}</span>
                <span className="flex items-center gap-1.5">
                  {isRecommended ? (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold font-mono uppercase tracking-wide bg-primary/10 text-primary">
                      Recommended
                    </span>
                  ) : null}
                  {chosen === t ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" aria-label="Chosen" />
                  ) : null}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {chosen ? (
        <div
          role="status"
          className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-600 dark:text-emerald-400"
        >
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
          Resume chosen: <span className="font-semibold">{chosen}</span>
        </div>
      ) : canChoose ? (
        <div className="flex items-center gap-3 pt-1">
          <Button onClick={onChoose} disabled={!selected || busy} className="min-w-40">
            {busy ? (
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
            ) : (
              <Check className="w-4 h-4" aria-hidden="true" />
            )}
            Continue with {selected ?? '…'}
          </Button>
          <span className="text-[11px] text-muted-foreground">Press Enter to confirm.</span>
        </div>
      ) : (
        <ReadOnlyNote>Resume selection unlocks after the answers step.</ReadOnlyNote>
      )}
    </div>
  );
}

// ─── Step 4: Assistant (placeholder — real panel lands with CP-6-04) ────────

function AssistantStep({
  sessionId,
  canOpen,
  formFilled,
}: {
  sessionId: string;
  canOpen: boolean;
  formFilled: boolean;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight flex items-center gap-2">
          <Bot className="w-4 h-4 text-primary" aria-hidden="true" /> Form-Fill Assistant
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          The live browser assistant fills the application form and reports checkpoints.
        </p>
      </div>

      <div className="bg-card border border-border/50 rounded-xl p-8 text-center space-y-3">
        <Bot className="w-8 h-8 text-muted-foreground/40 mx-auto" aria-hidden="true" />
        <p className="text-sm font-medium">Live assistant panel</p>
        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
          The embedded browser view, field-by-field fill progress, and checkpoint
          gates ship with CP-6-04. Until then, open the assistant surface directly —
          this step exists in the rail and advances once the form is filled.
        </p>
        {canOpen ? (
          <div className="flex justify-center pt-1">
            <Button asChild size="sm" variant="outline">
              <Link to={`/copilot/assistant/${sessionId}`}>
                Open Assistant
                <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
              </Link>
            </Button>
          </div>
        ) : null}
      </div>

      {formFilled ? (
        <div
          role="status"
          className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-600 dark:text-emerald-400"
        >
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
          Form filled — the application is ready for the final submit step.
        </div>
      ) : canOpen ? null : (
        <ReadOnlyNote>This step unlocks after a resume is chosen.</ReadOnlyNote>
      )}
    </div>
  );
}

// ─── Step 5: Submit ─────────────────────────────────────────────────────────

function SubmitStep({
  session,
  events,
  answersCount,
  opportunity,
  canSubmit,
  busy,
  onSubmit,
}: {
  session: CopilotSession;
  events: SessionEvent[];
  answersCount: number;
  opportunity: ReturnType<typeof useCopilotOpportunity>['data'];
  canSubmit: boolean;
  busy: boolean;
  onSubmit: () => void;
}) {
  const submitted = session.state === 'SUBMITTED';
  const errorId = 'submit-hold-note';

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight">Submit</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Final review before the application is sent.
        </p>
      </div>

      {/* Review */}
      <div className="bg-card border border-border/50 rounded-xl divide-y divide-border/50">
        <ReviewRow label="Opportunity" value={opportunity ? `${opportunity.title} · ${opportunity.company}` : session.opportunity_id} />
        <ReviewRow label="Session state" value={<StatusBadge status={session.state} />} />
        <ReviewRow label="Answers" value={`${answersCount} confirmed`} />
        <ReviewRow label="Resume" value={session.resume_id ?? '—'} />
        {session.submitted_at ? (
          <ReviewRow label="Submitted" value={new Date(session.submitted_at).toLocaleString()} />
        ) : null}
        {session.outcome ? (
          <ReviewRow label="Outcome" value={<StatusBadge status={session.outcome} />} />
        ) : null}
      </div>

      {submitted ? (
        <div
          role="status"
          className={cn(
            'rounded-xl border p-5 space-y-1.5',
            session.outcome
              ? 'border-emerald-500/30 bg-emerald-500/5'
              : 'border-border bg-card',
          )}
        >
          <div className="flex items-center gap-2">
            <CheckCircle2
              className={cn('w-4 h-4', session.outcome ? 'text-emerald-500' : 'text-muted-foreground')}
              aria-hidden="true"
            />
            <p className="text-sm font-semibold">
              {session.outcome ? 'Application submitted — outcome recorded' : 'Application submitted'}
            </p>
          </div>
          <p className="text-xs text-muted-foreground">
            {session.outcome
              ? `Outcome: ${session.outcome}${session.outcome_at ? ` (${new Date(session.outcome_at).toLocaleString()})` : ''}.`
              : 'Outcome is pending — this view refreshes automatically.'}
          </p>
        </div>
      ) : canSubmit ? (
        <div className="space-y-3">
          <HoldToConfirmButton
            disabled={busy}
            busy={busy}
            onConfirm={onSubmit}
            describedBy={errorId}
          />
          {busy ? <p className="text-xs text-muted-foreground">Submitting…</p> : null}
        </div>
      ) : (
        <ReadOnlyNote>Submit unlocks after the assistant fills the form.</ReadOnlyNote>
      )}

      {/* Event trail */}
      {events.length > 0 ? (
        <div className="bg-card border border-border/50 rounded-xl p-4 space-y-1.5">
          <h3 className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Session trail
          </h3>
          <ol className="space-y-1">
            {events.map((e) => (
              <li key={e.seq} className="flex items-center gap-2 text-[11px] font-mono">
                <span className="text-muted-foreground">
                  {new Date(e.occurred_at).toLocaleTimeString()}
                </span>
                <StatusBadge status={e.event_type} />
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2.5">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      <span className="text-xs font-medium text-foreground text-right">{value}</span>
    </div>
  );
}
