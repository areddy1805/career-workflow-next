import { useDeferredValue, useMemo, useState, type ReactNode } from 'react';
import {
  AlertCircle,
  BarChart3,
  Check,
  Database,
  Eye,
  GraduationCap,
  Loader2,
  Lock,
  Pencil,
  Save,
  Search,
  ShieldCheck,
  Unlock,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { RelativeTime } from '@/components/RelativeTime';
import { StatusBadge } from '@/components/StatusBadge';
import { confirmAnswer, lockAnswer, switchProfile } from '@/lib/api/copilot';
import { useAnswers } from '@/lib/hooks';
import type { StoredAnswer } from '@/lib/types/copilot';
import { cn } from '@/lib/utils';

// ─── Frozen constants (docs/application_copilot) ─────────────────────────────
// Profile set (06_ANSWER_BANK.md §5), AnswerStatus vocabulary (§3/§6),
// bias constants (11_DECISIONS.md D-028; 10_PROGRESS CP-7-03).
const PROFILES = [
  { id: 'ai', label: 'AI', description: 'Applied-AI / ML roles' },
  { id: 'fde', label: 'FDE', description: 'Forward-deployed engineer roles' },
  { id: 'generic', label: 'Generic', description: 'General software-engineering answers' },
] as const;

const STATUSES = ['auto', 'confirm', 'confirmed', 'locked', 'superseded'] as const;
const PROFILE_STORAGE_KEY = 'cw-copilot-profile';

// StatusBadge color overrides — global semantics (emerald=confirmed,
// amber=needs-confirm, blue=locked; auto/superseded keep neutral gray).
const STATUS_STYLE: Record<string, string> = {
  confirm: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  confirmed: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  locked: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
};

// CP-7-03 frozen constants — deterministic display only (no fetch).
const MAX_BIAS = 1.0;
const PROBABILITY_ADJUST = 0.15;
const BIAS_ENABLED = false; // LEARNING_BIAS_ENABLED — off by default (D-028: gates consumption, not collection)

function loadProfile(): string {
  try {
    const saved = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (saved && PROFILES.some((p) => p.id === saved)) return saved;
  } catch {
    // Storage unavailable (private mode) — fall through to default.
  }
  return 'ai';
}

function answerText(a: StoredAnswer): string {
  return typeof a.semantic_answer === 'string'
    ? a.semantic_answer
    : JSON.stringify(a.semantic_answer);
}

export default function Learning() {
  const [profileId, setProfileId] = useState<string>(loadProfile);
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);

  const [q, setQ] = useState('');
  const deferredQ = useDeferredValue(q);
  const [status, setStatus] = useState<string>('all');

  const answersQ = useAnswers({
    profile_id: profileId,
    q: deferredQ.trim() || undefined,
    status: status === 'all' ? undefined : status,
  });

  const [editingFp, setEditingFp] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState<{ fp: string; action: string } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const answers = answersQ.data ?? [];
  const filterActive = status !== 'all' || q.trim() !== '';

  // ── Profile switch: atomic namespace + resume swap (06 §5) ────────────────
  const handleProfileSwitch = async (id: string) => {
    if (id === profileId || switching) return;
    setSwitching(true);
    setSwitchError(null);
    try {
      await switchProfile(id); // server swaps the namespace atomically
      setProfileId(id); // queryKey change refetches the answer list
      try {
        localStorage.setItem(PROFILE_STORAGE_KEY, id);
      } catch {
        // Private mode — keep in-memory selection.
      }
      setEditingFp(null);
      setActionError(null);
    } catch (e) {
      setSwitchError(e instanceof Error ? e.message : 'Profile switch failed.');
    } finally {
      setSwitching(false);
    }
  };

  // ── Row mutations: every write refetches the list ─────────────────────────
  const runMutation = async (a: StoredAnswer, action: string, fn: () => Promise<unknown>) => {
    setBusy({ fp: a.question_fp, action });
    setActionError(null);
    try {
      await fn();
      await answersQ.refetch();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Answer update failed.');
    } finally {
      setBusy(null);
    }
  };

  const confirmRow = (a: StoredAnswer) =>
    runMutation(a, 'confirm', () =>
      confirmAnswer({
        question_fp: a.question_fp,
        profile_id: profileId,
        answer: a.semantic_answer,
        actor: 'user',
      }),
    );

  const saveEdit = (a: StoredAnswer) =>
    runMutation(a, 'save', async () => {
      await confirmAnswer({
        question_fp: a.question_fp,
        profile_id: profileId,
        answer: draft,
        actor: 'user', // stored as source=manual, status=confirmed (confirm.py)
      });
      setEditingFp(null);
    });

  const toggleLock = (a: StoredAnswer) =>
    runMutation(a, a.status === 'locked' ? 'unlock' : 'lock', () =>
      lockAnswer({ question_fp: a.question_fp, profile_id: profileId, locked: a.status !== 'locked' }),
    );

  // ── Signals overview: outcome_quality + use_count ARE the signal data ─────
  const stats = useMemo(() => {
    const answers = answersQ.data ?? [];
    const avg = (vals: number[]) =>
      vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
    const quality = answers
      .filter((r) => r.outcome_quality != null)
      .map((r) => r.outcome_quality as number);
    const conf = answers.filter((r) => r.confidence != null).map((r) => r.confidence as number);
    return {
      total: answers.length,
      confirmed: answers.filter((r) => r.status === 'confirmed').length,
      locked: answers.filter((r) => r.status === 'locked').length,
      avgQuality: avg(quality),
      avgConfidence: avg(conf),
      totalUses: answers.reduce((s, r) => s + r.use_count, 0),
    };
  }, [answersQ.data]);

  // ── Answer row ─────────────────────────────────────────────────────────────
  const renderRow = (a: StoredAnswer) => {
    const rowBusy = busy?.fp === a.question_fp;
    const busyAction = rowBusy ? busy.action : null;
    const label = a.canonical_label ?? a.question_fp;
    const isLocked = a.status === 'locked';
    const isSuperseded = a.status === 'superseded';
    const editable = typeof a.semantic_answer === 'string';
    const editing = editingFp === a.question_fp;

    return (
      <article
        key={a.question_fp}
        tabIndex={0}
        aria-label={`Answer ${label}, status ${a.status}`}
        className="rounded-xl border border-border/60 bg-card p-4 space-y-2.5 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[13px] font-semibold font-mono truncate">{label}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-1.5">
              <span>{a.category ?? 'uncategorized'}</span>
              <span aria-hidden="true">·</span>
              <span>source {a.source}</span>
              <span aria-hidden="true">·</span>
              <span>conf {(a.confidence ?? 0).toFixed(2)}</span>
              <span aria-hidden="true">·</span>
              <span>used {a.use_count}×</span>
              <span aria-hidden="true">·</span>
              <span>quality {(a.outcome_quality ?? 0).toFixed(2)}</span>
              <span aria-hidden="true">·</span>
              <span>
                {a.last_used_at ? <RelativeTime date={a.last_used_at} /> : 'never used'}
              </span>
            </p>
          </div>
          <StatusBadge status={a.status} className={STATUS_STYLE[a.status]} />
        </div>

        {editing ? (
          <div className="space-y-2">
            <label className="sr-only" htmlFor={`edit-${a.question_fp}`}>
              Edit answer {label}
            </label>
            <textarea
              id={`edit-${a.question_fp}`}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-[13px] font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={() => saveEdit(a)}
                disabled={rowBusy}
                aria-label={`Save edited answer ${label}`}
              >
                {rowBusy && busyAction === 'save' ? (
                  <Loader2 className="animate-spin" aria-hidden="true" />
                ) : (
                  <Save aria-hidden="true" />
                )}
                Save
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setEditingFp(null);
                  setActionError(null);
                }}
                disabled={rowBusy}
                aria-label={`Cancel editing answer ${label}`}
              >
                <X aria-hidden="true" /> Cancel
              </Button>
            </div>
          </div>
        ) : (
          <>
            <p className="text-[13px] text-foreground/90 whitespace-pre-wrap leading-relaxed">
              {answerText(a)}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {isSuperseded ? (
                <span className="text-[10px] text-muted-foreground/70 font-mono uppercase tracking-wide">
                  Superseded tombstone — no actions
                </span>
              ) : (
                <>
                  {!isLocked && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => confirmRow(a)}
                        disabled={rowBusy}
                        aria-label={`Confirm answer ${label}`}
                      >
                        {rowBusy && busyAction === 'confirm' ? (
                          <Loader2 className="animate-spin" aria-hidden="true" />
                        ) : (
                          <Check aria-hidden="true" />
                        )}
                        Confirm
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditingFp(a.question_fp);
                          setDraft(answerText(a));
                        }}
                        disabled={rowBusy || !editable}
                        aria-label={`Edit answer ${label}`}
                        title={editable ? undefined : 'Structured answers cannot be edited inline'}
                      >
                        <Pencil aria-hidden="true" /> Edit
                      </Button>
                    </>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => toggleLock(a)}
                    disabled={rowBusy}
                    aria-label={`${isLocked ? 'Unlock' : 'Lock'} answer ${label}`}
                  >
                    {rowBusy && (busyAction === 'lock' || busyAction === 'unlock') ? (
                      <Loader2 className="animate-spin" aria-hidden="true" />
                    ) : isLocked ? (
                      <Unlock aria-hidden="true" />
                    ) : (
                      <Lock aria-hidden="true" />
                    )}
                    {isLocked ? 'Unlock' : 'Lock'}
                  </Button>
                </>
              )}
            </div>
          </>
        )}
      </article>
    );
  };

  const currentProfile = PROFILES.find((p) => p.id === profileId);

  return (
    <div className="h-full flex flex-col bg-background text-sm">
      <header className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0 bg-background/95 backdrop-blur z-10">
        <div>
          <h1 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <GraduationCap className="w-4 h-4 text-primary" /> Learning
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Answer bank editor, profiles, evidence, and signals.
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-5xl mx-auto space-y-5 pb-8">
          {/* ── Profile switcher (atomic namespace swap, 06 §5) ── */}
          <SectionCard
            title="Profile"
            description="Answers are namespaced per profile; switching atomically swaps the namespace and resume mapping (06_ANSWER_BANK.md §5)."
          >
            <div className="flex flex-wrap items-center gap-4">
              <div
                role="radiogroup"
                aria-label="Answer profile"
                className="inline-flex rounded-lg border border-border/60 bg-muted/30 p-1 gap-1"
              >
                {PROFILES.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    role="radio"
                    aria-checked={profileId === p.id}
                    disabled={switching}
                    onClick={() => handleProfileSwitch(p.id)}
                    className={cn(
                      'px-3 py-1.5 rounded-md text-[12px] font-semibold transition-colors',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      profileId === p.id
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground" role="status" aria-live="polite">
                {switching
                  ? 'Switching profile…'
                  : switchError
                    ? `Switch failed: ${switchError}`
                    : currentProfile
                      ? `${currentProfile.description} — persisted in localStorage[${PROFILE_STORAGE_KEY}]`
                      : ''}
              </p>
            </div>
          </SectionCard>

          {/* ── Answer bank editor ── */}
          <SectionCard
            title="Answer bank"
            description="Search by canonical label, filter by status, and confirm / lock / edit per profile."
          >
            <div className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-end gap-3">
                <div className="flex-1 space-y-1">
                  <label htmlFor="answer-search" className="text-xs font-medium text-muted-foreground">
                    Search canonical label
                  </label>
                  <div className="relative">
                    <Search
                      className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <input
                      id="answer-search"
                      type="search"
                      value={q}
                      onChange={(e) => setQ(e.target.value)}
                      placeholder="e.g. experience.rag_years"
                      className="w-full rounded-md border border-input bg-background pl-8 pr-3 py-2 text-[13px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <span className="text-xs font-medium text-muted-foreground block">
                    Filter by status
                  </span>
                  <div
                    role="group"
                    aria-label="Filter by status"
                    className="flex flex-wrap items-center gap-1.5"
                  >
                    {['all', ...STATUSES].map((s) => (
                      <button
                        key={s}
                        type="button"
                        aria-pressed={status === s}
                        onClick={() => setStatus(s)}
                        className={cn(
                          'px-2 py-1 rounded-md text-[11px] font-semibold uppercase tracking-wide font-mono transition-colors',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                          status === s
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground hover:bg-muted/70',
                        )}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {actionError && (
                <p
                  role="alert"
                  className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400"
                >
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                  {actionError}
                </p>
              )}

              {answersQ.isLoading && (
                <div className="space-y-3" aria-label="Loading answers">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-24 bg-muted/50 rounded-xl animate-pulse" />
                  ))}
                </div>
              )}

              {answersQ.isError && (
                <div className="bg-card border border-border/60 rounded-xl p-8 text-center space-y-3 shadow-sm">
                  <AlertCircle className="w-8 h-8 text-red-500/70 mx-auto" aria-hidden="true" />
                  <p className="text-sm font-medium">Could not load answers</p>
                  <p className="text-xs text-muted-foreground break-words">
                    {answersQ.error?.message ?? 'Unknown error.'}
                  </p>
                  <Button variant="outline" size="sm" onClick={() => answersQ.refetch()}>
                    <Loader2 className="w-3.5 h-3.5" aria-hidden="true" /> Retry
                  </Button>
                </div>
              )}

              {!answersQ.isLoading && !answersQ.isError && answers.length === 0 && (
                <div className="bg-card border border-border/60 rounded-xl p-8 text-center space-y-3 shadow-sm">
                  <Database className="w-8 h-8 text-muted-foreground/40 mx-auto" aria-hidden="true" />
                  <p className="text-sm font-medium">No answers</p>
                  <p className="text-xs text-muted-foreground">
                    {filterActive
                      ? 'No answers match the current search and status filter.'
                      : 'No stored answers for this profile yet. Answers are stored when confirmed or used.'}
                  </p>
                </div>
              )}

              {!answersQ.isLoading && !answersQ.isError && answers.length > 0 && (
                <div className="space-y-3">{answers.map(renderRow)}</div>
              )}
            </div>
          </SectionCard>

          {/* ── Signals overview (CP-7-02: derivable from stores) ── */}
          <SectionCard
            title="Learning signals"
            description="The answer bank columns below ARE the signal data: outcome_quality and use_count are written by the learning loop (CP-7-04 feedback), so this view is derived from the same fetch — no separate endpoint."
          >
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <StatTile label="Answers in view" value={String(stats.total)} />
              <StatTile label="Confirmed" value={String(stats.confirmed)} />
              <StatTile label="Locked" value={String(stats.locked)} />
              <StatTile
                label="Avg outcome quality"
                value={stats.avgQuality == null ? '—' : stats.avgQuality.toFixed(2)}
              />
              <StatTile
                label="Avg confidence"
                value={stats.avgConfidence == null ? '—' : stats.avgConfidence.toFixed(2)}
              />
              <StatTile label="Total uses" value={String(stats.totalUses)} />
            </div>
            <div className="grid sm:grid-cols-2 gap-3 mt-3">
              <PendingPh8Card
                title="Provider / ATS conversion"
                body="Interview/offer rates by provider, ATS type, and resume profile are derivable from copilot_learning_outcomes (conversion_signals: total / applied / interview / offer + interview_rate + offer_rate), but no analytics endpoint is frozen yet."
                next="CP-8-01 adds /api/copilot/analytics — this section lands then."
              />
              <PendingPh8Card
                title="Ranking bias analytics"
                body="Persisted learning_bias readings and their contribution to brief probability will be surfaced by the same CP-8-01 analytics API."
                next="Until then, the frozen constants are shown in the Ranking bias card below."
              />
            </div>
          </SectionCard>

          {/* ── Evidence viewer (read-only, no fetch) ── */}
          <SectionCard
            title="Candidate evidence"
            description="CANDIDATE_EVIDENCE — pipeline-owned, surfaced read-only."
          >
            <div className="flex items-start gap-3">
              <Eye
                className="w-4 h-4 text-primary shrink-0 mt-0.5"
                aria-hidden="true"
              />
              <div className="space-y-1.5 text-[13px] text-muted-foreground">
                <p>
                  Candidate evidence is ingested and owned by the pipeline (resume / repository
                  sources); the UI never writes it — pipeline writes flow only through the workflow
                  transition / ledger APIs (ADR-007).
                </p>
                <p>
                  There is no frozen evidence endpoint in the §7.9 API surface, so this view is
                  rendered read-only and statically — no fetch. Answers reference their evidence via
                  the per-row <code className="font-mono text-xs">source</code> and provenance shown
                  in the answer bank above.
                </p>
              </div>
            </div>
          </SectionCard>

          {/* ── Ranking bias view (persisted learning_bias; deterministic display) ── */}
          <SectionCard
            title="Ranking bias"
            description="Persisted learning_bias contributions (CP-7-03) — read-only, deterministic display, no fetch."
          >
            <div className="flex items-start gap-3">
              <ShieldCheck
                className="w-4 h-4 text-primary shrink-0 mt-0.5"
                aria-hidden="true"
              />
              <div className="space-y-2 text-[13px] text-muted-foreground flex-1">
                <p>
                  Bias contributions are persisted in{' '}
                  <code className="font-mono text-xs">copilot_learning_weights</code> (row{' '}
                  <code className="font-mono text-xs">learning_bias</code>), written by{' '}
                  <code className="font-mono text-xs">apply_outcome_feedback</code> as a monotonic
                  bounded EMA — explore early, exploit later, zero randomness (D-028).
                </p>
                <div className="grid sm:grid-cols-3 gap-2 pt-1">
                  <div className="rounded-lg border border-border/60 p-2.5">
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                      Gate
                    </p>
                    <p className="text-xs font-mono mt-0.5">
                      LEARNING_BIAS_ENABLED = {BIAS_ENABLED ? 'on' : 'off'}
                    </p>
                    <p className="text-[10px] text-muted-foreground/70 mt-1">
                      Off by default; gates consumption (brief probability, ranking), not collection
                      — rollback is flag-off → identical to today.
                    </p>
                  </div>
                  <div className="rounded-lg border border-border/60 p-2.5">
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                      Max bias
                    </p>
                    <p className="text-xs font-mono mt-0.5">±{MAX_BIAS.toFixed(1)}</p>
                    <p className="text-[10px] text-muted-foreground/70 mt-1">
                      EMA clamp bound — engine also clamps providers to the same range.
                    </p>
                  </div>
                  <div className="rounded-lg border border-border/60 p-2.5">
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                      Brief probability adjust
                    </p>
                    <p className="text-xs font-mono mt-0.5">±{PROBABILITY_ADJUST.toFixed(2)}</p>
                    <p className="text-[10px] text-muted-foreground/70 mt-1">
                      adjusted_probability bound — identity when the flag is off.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}

// ─── Presentational helpers ───────────────────────────────────────────────────

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-card border border-border/60 rounded-xl shadow-sm">
      <div className="px-4 py-3 border-b border-border/50">
        <h2 className="text-sm font-semibold">{title}</h2>
        {description && (
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        )}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/60 p-3 bg-muted/20">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
        {label}
      </p>
      <p className="text-base font-mono mt-1">{value}</p>
    </div>
  );
}

function PendingPh8Card({ title, body, next }: { title: string; body: string; next: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border/70 p-3.5 space-y-1.5">
      <div className="flex items-center gap-2">
        <BarChart3 className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" />
        <p className="text-xs font-semibold">{title}</p>
        <span className="ml-auto px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[10px] font-mono uppercase tracking-wide">
          Pending PH8
        </span>
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed">{body}</p>
      <p className="text-[10px] text-muted-foreground/70">{next}</p>
    </div>
  );
}
