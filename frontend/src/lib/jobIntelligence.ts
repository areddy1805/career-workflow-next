// Job Intelligence helpers — pure, deterministic projections of the
// GET /api/jobs/{id} inspection payload.  No parsing, no scoring, no LLM:
// every value below is derived from fields the backend already provides,
// and sections whose data is missing simply do not render.

export type RecommendationTone = 'apply' | 'manual' | 'skip' | 'done';

export interface Recommendation {
  label: string;
  tone: RecommendationTone;
  detail?: string;
}

/** Deterministic APPLY / MANUAL REVIEW / SKIP derivation from existing data. */
export function deriveRecommendation(details: any): Recommendation | null {
  if (!details) return null;

  const lc = details.lifecycle?.current_state as string | undefined;
  if (lc === 'SUBMITTED' || lc === 'ALREADY_APPLIED') {
    return { label: 'ALREADY APPLIED', tone: 'done', detail: `Lifecycle state: ${lc}` };
  }
  if (lc === 'ROUTED_MANUAL') {
    return { label: 'MANUAL REVIEW', tone: 'manual', detail: 'Queued for manual review' };
  }
  if (lc === 'APPLICATION_FAILED') {
    return {
      label: 'MANUAL REVIEW',
      tone: 'manual',
      detail: 'Auto-apply failed — questionnaire needs human review',
    };
  }
  if (lc === 'DEFERRED') {
    return {
      label: 'DEFERRED',
      tone: 'skip',
      detail: 'Quota-constrained in a prior run — candidate for a future run',
    };
  }

  const strategy = details.routing?.application_strategy as string | undefined;
  if (strategy && strategy !== 'auto') {
    return { label: 'MANUAL REVIEW', tone: 'manual', detail: `Strategy: ${strategy}` };
  }

  const fit = details.classification?.fit_class as string | undefined;
  const score = details.score_and_ranking?.score as number | undefined;
  const aiScore = details.score_and_ranking?.ai_score as number | undefined;
  const numeric = typeof score === 'number' ? score : typeof aiScore === 'number' ? aiScore : undefined;

  if (fit === 'high' || fit === 'good' || (typeof numeric === 'number' && numeric >= 75)) {
    return { label: 'APPLY', tone: 'apply', detail: `Fit: ${fit ?? 'n/a'} · score: ${numeric ?? 'n/a'}` };
  }
  if (typeof numeric === 'number' && numeric >= 50) {
    return { label: 'CONSIDER', tone: 'manual', detail: `Score: ${numeric}` };
  }
  if (typeof numeric === 'number') {
    return { label: 'SKIP', tone: 'skip', detail: `Score: ${numeric}` };
  }
  return null; // not derivable from available data — hide
}

export interface SalaryView {
  label: string;
  currency?: string;
}

/** Compact salary label from jd.salary (comp fields or the raw cache dict). */
export function salaryLabel(salary: any): string | null {
  if (!salary) return null;
  const min = salary.min ?? salary.raw_cache?.minimumSalary;
  const max = salary.max ?? salary.raw_cache?.maximumSalary;
  const currency = salary.currency ?? salary.raw_cache?.currency;
  if (min == null && max == null && !salary.notes) return null;
  const parts: string[] = [];
  if (min != null && max != null) parts.push(`${min.toLocaleString('en-IN')} – ${max.toLocaleString('en-IN')}`);
  else if (min != null) parts.push(`${min.toLocaleString('en-IN')}+`);
  else if (max != null) parts.push(`up to ${max.toLocaleString('en-IN')}`);
  if (salary.notes) parts.push(salary.notes);
  const suffix = currency ? ` ${currency}` : '';
  return parts.join(' · ') + suffix;
}

// ─── Workflow-aware actions ───────────────────────────────────────────────────
// One derivation of the action set for the canonical Job Inspector, shared by
// the Jobs panel and the Applications drawer.  Actions are gated by the job's
// actual state so a terminal/applied job never offers "Mark Applied" and a
// deferred job is never offered blind re-application.

export type ActionId =
  | 'mark-applied' | 'reject' | 'skip' | 'dismiss'
  | 'move-manual' | 'move-ats' | 'open' | 'json';

export interface InspectorAction {
  id: ActionId;
  label: string;
  tone: 'primary' | 'danger' | 'outline' | 'ghost';
}

const APPLIED_STATES = new Set([
  'SUBMITTED', 'ALREADY_APPLIED', 'applied', 'already_applied',
]);
const CLOSED_STATES = new Set([
  'REJECTED', 'ARCHIVED', 'rejected', 'archived', 'dismissed',
]);

export function deriveAllowedActions(
  details: any,
  variant: 'queue' | 'jobs',
): InspectorAction[] {
  if (!details) return [{ id: 'json', label: 'View JSON', tone: 'ghost' }];
  const state =
    details.lifecycle?.current_state ??
    details.status?.workflow_status ??
    details.status?.status;
  const applied = APPLIED_STATES.has(state);
  const closed = CLOSED_STATES.has(state);
  const acts: InspectorAction[] = [];

  if (variant === 'queue') {
    // Queue review: the item sits in a human-action queue by definition.
    if (!applied && !closed) {
      acts.push(
        { id: 'mark-applied', label: 'Mark Applied', tone: 'primary' },
        { id: 'skip', label: 'Skip', tone: 'danger' },
        { id: 'dismiss', label: 'Dismiss', tone: 'ghost' },
      );
    }
  } else {
    // Jobs panel: actions follow the pipeline state.
    if (state === 'DEFERRED') {
      // Quota-deferred — revisit later or re-route, never blind apply.
      acts.push(
        { id: 'move-manual', label: 'Manual Review Queue', tone: 'outline' },
        { id: 'move-ats', label: 'ATS Queue', tone: 'outline' },
      );
    } else if (state === 'APPLICATION_FAILED') {
      // Auto-apply failed — the human task is review, not blind retry.
      acts.push({ id: 'move-manual', label: 'Manual Review Queue', tone: 'outline' });
    } else if (!applied && !closed) {
      acts.push(
        { id: 'mark-applied', label: 'Mark Applied', tone: 'primary' },
        { id: 'reject', label: 'Reject', tone: 'danger' },
        { id: 'move-manual', label: 'Manual Review Queue', tone: 'outline' },
        { id: 'move-ats', label: 'ATS Queue', tone: 'outline' },
      );
    }
  }
  return acts;
}

/** Why this job sits in a manual/ATS queue — from existing queue + lifecycle
 * evidence, never invented. */
export function reviewContext(details: any): { mode: string; why: string } | null {
  if (!details) return null;
  const entry = details.routing?.manual_queue_entries?.[0];
  const modeRaw = entry?.mode ?? details.routing?.ats_type;
  const mode =
    modeRaw === 'MANUAL_REVIEW' ? 'Manual Review'
    : modeRaw === 'EXTERNAL' || modeRaw === 'ATS' ? 'ATS Required'
    : modeRaw
      ? String(modeRaw)
      : 'Attention';
  const why =
    entry?.reason ??
    details.lifecycle?.last_reason ??
    details.status?.last_error ??
    '';
  if (!entry && !details.lifecycle?.last_reason && !details.status?.last_error) return null;
  return { mode, why: String(why || 'Pending human decision.') };
}
