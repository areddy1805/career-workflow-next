// ─── Canonical Job Inspector ─────────────────────────────────────────────────
// ONE reusable job-detail surface shared by the Jobs page (right panel) and the
// Applications/Inbox page (drawer).  It is a pure consumer of the existing
// GET /api/jobs/{id} payload ({ overview, events, details }) — no new store,
// no JD parser, no duplicated scoring/lifecycle logic, no invented fields.
// Sections with no available data are hidden; actions are derived from the
// job's real state so inappropriate actions never render.

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { transitionQueueJob, moveQueueJob } from '@/lib/api';
import { cn } from '@/lib/utils';
import { StatusBadge } from '@/components/StatusBadge';import { RelativeTime } from '@/components/RelativeTime';
import { Button } from '@/components/ui/button';
import {
  AlertCircle, CheckCircle, ExternalLink, Loader2, SkipForward, XCircle, FolderOpen, Eye,
} from 'lucide-react';
import {
  deriveRecommendation, deriveAllowedActions, salaryLabel, reviewContext,
  type InspectorAction, type ActionId,
} from '@/lib/jobIntelligence';

function scoreColor(score: number | null | undefined) {
  if (score == null) return 'text-muted-foreground';
  if (score >= 70) return 'text-healthy';
  if (score >= 40) return 'text-degraded';
  return 'text-failed';
}

// ─── Small section primitives (incumbent vocabulary) ─────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
      {children}
    </p>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="text-xs text-foreground/80 leading-relaxed flex gap-2">
          <span className="text-primary/60 mt-1">•</span>
          <span className="min-w-0">{item}</span>
        </li>
      ))}
    </ul>
  );
}

function Chip({ value, tone = 'default' }: { value: string; tone?: 'default' | 'gap' }) {
  return (
    <span className={cn(
      'inline-block rounded px-2 py-0.5 text-[11px] border',
      tone === 'gap'
        ? 'bg-failed/10 border-failed/30 text-failed/90'
        : 'bg-muted/50 border-border/60 text-foreground/80',
    )}>
      {value}
    </span>
  );
}

function FactCell({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="bg-muted/30 rounded p-3 min-w-0">
      <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
      <p className="text-xs font-medium break-words">{value}</p>
    </div>
  );
}

// ─── Canonical content ────────────────────────────────────────────────────────

export function JobInspectorContent({
  data,
  jobId,
  variant,
  onOpenJson,
  onTransitioned,
}: {
  data: any;
  jobId: string;
  variant: 'queue' | 'jobs';
  onOpenJson: () => void;
  onTransitioned?: () => void;
}) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<ActionId | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const ov = data?.overview ?? {};
  const det = data?.details ?? {};
  const jd = det.jd ?? {};
  const skills = det.skills ?? {};
  const classification = det.classification ?? {};
  const ranking = det.score_and_ranking ?? {};
  const location = det.location ?? {};
  const urls = det.source_and_urls ?? {};
  const lifecycle = det.lifecycle ?? {};
  const status = det.status ?? {};

  const fullJd = jd.description_plain || null;
  const salary = salaryLabel(jd.salary);
  const recommendation = deriveRecommendation(det);
  const context = reviewContext(det);
  const actions = deriveAllowedActions(det, variant);

  const jobUrl =
    urls.apply_url || urls.canonical_url || urls.careers_url || ov.apply_url || null;

  const fitChips = [
    classification.fit_class && `Fit: ${classification.fit_class}`,
    classification.role_family && `Role family: ${classification.role_family}`,
    classification.ai_depth != null && `AI depth: ${classification.ai_depth}`,
    classification.subtrack && `Subtrack: ${classification.subtrack}`,
    classification.industry && `Industry: ${classification.industry}`,
    typeof ranking.interview_probability === 'number' &&
      `P(interview) ${Math.round(ranking.interview_probability * 100)}%`,
  ].filter(Boolean) as string[];

  const skillChips: string[] = [
    ...(Array.isArray(skills.required) ? skills.required : []),
    ...(Array.isArray(skills.preferred_skills) ? skills.preferred_skills : []),
    ...(Array.isArray(skills.tags) ? skills.tags : []),
  ];
  const gapChips: string[] = Array.isArray(skills.missing_skills) ? skills.missing_skills : [];

  const locStr =
    typeof location === 'string' ? location
    : typeof location?.location === 'string' ? location.location
    : typeof location?.city === 'string' ? location.city
    : '';
  const metaParts = [ov.location || locStr, urls.provider || ov.source]
    .filter(p => p != null && String(p).trim() !== '')
    .map(p => String(p));

  const locBits = [
    locStr,
    location?.city && `City: ${location.city}`,
    location?.region && `Region: ${location.region}`,
    location?.country && `Country: ${location.country}`,
    location?.remote === true && 'Remote',
    location?.remote === false && 'On-site',
    location?.relocation_required === true && 'Relocation required',
  ].filter(Boolean) as string[];

  const attempts = Array.isArray(lifecycle.transitions) ? lifecycle.transitions.length : 0;
  const unresolved = det.questionnaire?.unresolved ?? [];
  const rejectionReasons = Array.isArray(lifecycle.rejection_or_deferral_reasons)
    ? lifecycle.rejection_or_deferral_reasons
    : [];
  const scoreLabel =
    ov.score != null ? `${ov.score} / 100`
    : classification.fit_class ? `Fit: ${classification.fit_class}`
    : null;
  const roleProfile = [classification.role_family, classification.subtrack]
    .filter(Boolean)
    .join(' · ') || null;

  const runAction = async (id: ActionId, fn: () => Promise<unknown>) => {
    setBusy(id);
    setActionError(null);
    try {
      await fn();
      queryClient.invalidateQueries({ queryKey: ['queue'] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['ledger'] });
      onTransitioned?.();
    } catch (e: any) {
      setActionError(e?.message || 'Action failed — this job may not allow this transition from its current state.');
    } finally {
      setBusy(null);
    }
  };

  const actionHandlers: Record<ActionId, (() => Promise<unknown>) | null> = {
    'mark-applied': () => transitionQueueJob(jobId, 'APPLIED', 'Job Inspector'),
    'skip':         () => transitionQueueJob(jobId, 'REJECTED', 'Job Inspector'),
    'dismiss':      () => transitionQueueJob(jobId, 'ARCHIVED', 'Job Inspector'),
    'reject':       () => transitionQueueJob(jobId, 'REJECTED', 'Job Inspector'),
    'move-manual':  () => moveQueueJob(jobId, 'manual_review'),
    'move-ats':     () => moveQueueJob(jobId, 'external_apply'),
    'open':         null,
    'json':         null,
  };

  const actionTone: Record<InspectorAction['tone'], string> = {
    primary: 'bg-healthy text-background border-0 hover:bg-healthy/90',
    danger:  'text-failed border-failed/40 hover:bg-failed/10',
    outline: 'text-foreground/80 border-border/60 hover:bg-muted/40',
    ghost:   'text-muted-foreground hover:text-foreground',
  };

  const renderAction = (a: InspectorAction) => {
    if (a.id === 'open') return null; // rendered separately, first
    const Icon =
      a.id === 'mark-applied' ? CheckCircle
      : a.id === 'reject' || a.id === 'skip' ? SkipForward
      : a.id === 'dismiss' ? XCircle
      : a.id === 'move-manual' || a.id === 'move-ats' ? FolderOpen
      : Eye;
    return (
      <Button
        key={a.id}
        variant={a.tone === 'primary' || a.tone === 'ghost' ? (a.tone === 'primary' ? 'default' : 'ghost') : 'outline'}
        size="sm"
        className={cn('h-8 text-xs gap-1.5', a.tone !== 'primary' && a.tone !== 'ghost' && actionTone[a.tone])}
        onClick={() => { const fn = actionHandlers[a.id]; if (fn) runAction(a.id, fn); }}
        disabled={busy != null}
      >
        {busy === a.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Icon className="w-3 h-3" />}
        {a.label}
      </Button>
    );
  };

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Header — always visible while content scrolls */}
      <header className="shrink-0 border-b border-border/40 px-5 pt-4 pb-3 pr-12">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-bold tracking-tight leading-snug break-words">{ov.title || det.title}</h2>
            <p className="text-sm text-muted-foreground mt-1 leading-snug">
              <span className="font-medium text-foreground">{ov.company || det.company}</span>
              {metaParts.map(part => <span key={part}> · <span>{part}</span></span>)}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <div className="flex items-center gap-2">
              <StatusBadge status={ov.workflow_status ?? ov.status ?? 'UNKNOWN'} />
              {ov.score != null && (
                <span className={cn('text-xs font-mono font-bold tabular-nums', scoreColor(ov.score))}>
                  {ov.score}
                </span>
              )}
            </div>
            {lifecycle.current_state && (
              <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
                {lifecycle.current_state}
              </span>
            )}
          </div>
        </div>
        {/* Review context strip — why this job needs a human */}
        {context && (
          <div className="mt-3 flex items-start gap-2 bg-amber-500/10 border border-amber-500/30 rounded-md px-3 py-2">
            <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-500" />
            <p className="text-xs text-foreground/80 leading-relaxed">
              <span className="font-semibold text-amber-500">{context.mode}</span>
              {context.why ? <span className="text-muted-foreground"> — {context.why}</span> : null}
            </p>
          </div>
        )}
      </header>

      {/* Actions — always visible */}
      <div className="shrink-0 border-b border-border/40 px-5 py-2.5 bg-secondary/20 flex flex-wrap items-center gap-2">
        {jobUrl && (
          <Button
            variant="outline" size="sm" className="h-8 text-xs gap-1.5"
            onClick={() => window.open(String(jobUrl), '_blank', 'noopener,noreferrer')}
          >
            <ExternalLink className="w-3 h-3" /> Open Job
          </Button>
        )}
        {actions.filter(a => a.id !== 'json').map(renderAction)}
        <Button variant="ghost" size="sm" className="h-8 text-xs gap-1.5 ml-auto text-muted-foreground" onClick={onOpenJson}>
          <Eye className="w-3 h-3" /> View JSON
        </Button>
      </div>

      {actionError && (
        <div className="shrink-0 flex items-start gap-2 text-xs text-destructive bg-destructive/10 border-b border-destructive/20 px-5 py-2.5">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Scrollable intelligence body — one scroll region, no nested scrollbars */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="px-5 py-5 space-y-6">

          {/* Job Snapshot — decision facts first */}
          {(scoreLabel || jd.experience_required || salary || jd.employment_type || locBits.length > 0 || ov.posted_date || ov.priority || roleProfile) && (
            <section>
              <SectionTitle>Job Snapshot</SectionTitle>
              <div className="grid grid-cols-2 gap-3">
                <FactCell label="Score / Fit" value={scoreLabel} />
                <FactCell label="Experience" value={jd.experience_required || null} />
                <FactCell label="Salary / Compensation" value={salary || null} />
                <FactCell label="Employment" value={jd.employment_type || null} />
                <FactCell label="Location / Work Mode" value={locBits.join(' · ') || null} />
                <FactCell label="Posted" value={ov.posted_date || null} />
                <FactCell label="Priority" value={ov.priority || classification.priority || null} />
                <FactCell label="Role / Profile" value={roleProfile} />
              </div>
            </section>
          )}

          {/* Workflow / Review Context — why this job needs a human */}
          {(context || lifecycle.last_reason || status.last_error || attempts > 0 || unresolved.length > 0 || rejectionReasons.length > 0) && (
            <section>
              <SectionTitle>Workflow / Review Context</SectionTitle>
              <div className="space-y-2.5">
                {lifecycle.current_state && (
                  <p className="text-xs">
                    <span className="text-muted-foreground">Current state: </span>
                    <span className="font-mono text-foreground/90">{lifecycle.current_state}</span>
                  </p>
                )}
                {context?.why && context.why !== 'Pending human decision.' && (
                  <p className="text-xs text-foreground/80 leading-relaxed">
                    <span className="text-muted-foreground">{context.mode}: </span>{context.why}
                  </p>
                )}
                {status.last_error && (
                  <p className="text-xs text-failed/90 leading-relaxed">
                    <span className="text-muted-foreground">Last error: </span>{status.last_error}
                  </p>
                )}
                {attempts > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {attempts} lifecycle transition{attempts !== 1 ? 's' : ''} on record
                    {lifecycle.terminal_at ? ` · terminal ${new Date(lifecycle.terminal_at).toLocaleString()}` : ''}
                  </p>
                )}
                {rejectionReasons.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                      Deferral / rejection reasons
                    </p>
                    <BulletList items={rejectionReasons.slice(0, 8)} />
                  </div>
                )}
                {unresolved.length > 0 && (
                  <div className="bg-muted/20 border border-border/40 rounded-md p-3">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                      Unresolved questionnaire ({unresolved.length})
                    </p>
                    <ul className="space-y-1.5">
                      {unresolved.slice(0, 12).map((q: any, i: number) => (
                        <li key={i} className="text-xs text-foreground/80 leading-relaxed flex gap-2">
                          <span className="text-amber-500 mt-1">•</span>
                          <span className="min-w-0">{q.question || q.question_id}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Job Summary */}
          {jd.summary && (
            <section>
              <SectionTitle>Job Summary</SectionTitle>
              <p className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap">{jd.summary}</p>
            </section>
          )}

          {/* Decision Intelligence */}
          {(recommendation || ranking.ai_reason || gapChips.length > 0 || det.routing?.application_strategy || fitChips.length > 0 || (Array.isArray(jd.domain_knowledge) && jd.domain_knowledge.length > 0)) && (
            <section>
              <SectionTitle>Decision Intelligence</SectionTitle>
              <div className="space-y-3">
                {recommendation && (
                  <div className={cn(
                    'border rounded-md px-3 py-2 flex items-center gap-2',
                    recommendation.tone === 'apply' && 'bg-healthy/15 border-healthy/50 text-healthy',
                    recommendation.tone === 'manual' && 'bg-amber-500/10 border-amber-500/50 text-amber-500',
                    recommendation.tone === 'done' && 'bg-muted/40 border-border text-muted-foreground',
                    recommendation.tone === 'skip' && 'bg-failed/10 border-failed/50 text-failed',
                  )}>
                    <span className="text-[10px] font-semibold uppercase tracking-wider opacity-80">Recommendation</span>
                    <span className="text-xs font-bold">{recommendation.label}</span>
                    {recommendation.detail && (
                      <span className="text-[11px] opacity-75 ml-auto text-right">{recommendation.detail}</span>
                    )}
                  </div>
                )}
                {fitChips.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {fitChips.map((c, i) => <Chip key={i} value={c} />)}
                  </div>
                )}
                {ranking.ai_reason && (
                  <p className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap">
                    <span className="text-muted-foreground">Why it matches: </span>{ranking.ai_reason}
                  </p>
                )}
                {Array.isArray(jd.domain_knowledge) && jd.domain_knowledge.length > 0 && (
                  <p className="text-xs text-foreground/80 leading-relaxed">
                    <span className="text-muted-foreground">Domain knowledge: </span>{jd.domain_knowledge.join(', ')}
                  </p>
                )}
                {gapChips.length > 0 && (
                  <p className="text-xs text-failed/90 leading-relaxed">
                    Gaps / concerns: {gapChips.join(', ')}
                  </p>
                )}
                {det.routing?.application_strategy && (
                  <p className="text-xs text-muted-foreground">
                    Target strategy: {det.routing.application_strategy}
                  </p>
                )}
              </div>
            </section>
          )}

          {/* Key Responsibilities */}
          {Array.isArray(jd.responsibilities) && jd.responsibilities.length > 0 && (
            <section>
              <SectionTitle>Key Responsibilities</SectionTitle>
              <BulletList items={jd.responsibilities} />
            </section>
          )}

          {/* Requirements / Qualifications */}
          {(Array.isArray(jd.requirements) && jd.requirements.length > 0) || jd.qualifications ? (
            <section>
              <SectionTitle>Requirements / Qualifications</SectionTitle>
              {Array.isArray(jd.requirements) && jd.requirements.length > 0 ? (
                <BulletList items={jd.requirements} />
              ) : (
                <p className="text-xs text-foreground/80 leading-relaxed">{jd.qualifications}</p>
              )}
            </section>
          ) : null}

          {/* Skills */}
          {skillChips.length + gapChips.length > 0 && (
            <section>
              <SectionTitle>Skills / Technologies</SectionTitle>
              <div className="flex flex-wrap gap-1.5">
                {skillChips.map((s, i) => <Chip key={i} value={String(s)} />)}
                {gapChips.map((s, i) => <Chip key={`gap-${i}`} value={`${s} (gap)`} tone="gap" />)}
              </div>
            </section>
          )}

          {/* Full Job Description — normalized readable text; honest empty state */}
          <section>
            <SectionTitle>Full Job Description</SectionTitle>
            {fullJd ? (
              <pre className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap font-sans bg-muted/20 border border-border/40 rounded p-3">
                {fullJd}
              </pre>
            ) : (
              <div className="bg-muted/20 border border-dashed border-border/40 rounded-md p-4 text-xs text-muted-foreground leading-relaxed">
                Full job description is not available for this job. The review reason, score, and source links above are
                all the information stored for it.
              </div>
            )}
          </section>

          {/* Lifecycle History */}
          {Array.isArray(lifecycle.transitions) && lifecycle.transitions.length > 0 && (
            <section>
              <SectionTitle>Lifecycle History</SectionTitle>
              <div className="space-y-0 relative before:absolute before:left-[5px] before:top-0 before:h-full before:w-px before:bg-border/50">
                {lifecycle.transitions.map((tr: any, i: number) => (
                  <div key={i} className="relative pl-5 py-1.5">
                    <div className="absolute left-[2px] top-2.5 w-2 h-2 rounded-full bg-border border-2 border-background z-10" />
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono font-medium text-foreground/90">{String(tr.to_state)}</span>
                      <span className="text-[10px] text-muted-foreground">
                        <RelativeTime date={tr.timestamp} />
                      </span>
                    </div>
                    {tr.reason && <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">{String(tr.reason)}</p>}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Application History */}
          {Array.isArray(data.events) && data.events.length > 0 && (
            <section>
              <SectionTitle>Application History</SectionTitle>
              <div className="space-y-0 relative before:absolute before:left-[5px] before:top-0 before:h-full before:w-px before:bg-border/50">
                {data.events.map((evt: any, i: number) => (
                  <div key={i} className="relative pl-5 py-1.5">
                    <div className="absolute left-[2px] top-2.5 w-2 h-2 rounded-full bg-border border-2 border-background z-10" />
                    <div className="flex items-center gap-2 flex-wrap">
                      <StatusBadge status={evt.status} />
                      <span className="text-[10px] text-muted-foreground">
                        <RelativeTime date={evt.created_at ?? evt.timestamp} />
                      </span>
                    </div>
                    {evt.detail && <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">{evt.detail}</p>}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Source & URLs */}
          {(urls.provider || jobUrl) && (
            <section>
              <SectionTitle>Source & URLs</SectionTitle>
              <div className="space-y-1">
                {urls.provider && <p className="text-xs text-foreground/80">Provider: {urls.provider}</p>}
                {[urls.apply_url, urls.canonical_url, urls.careers_url].filter(Boolean).map((u, i) => (
                  <a key={i} href={String(u)} target="_blank" rel="noreferrer"
                     className="block text-xs text-primary/90 hover:underline truncate">
                    {String(u)}
                  </a>
                ))}
              </div>
            </section>
          )}

        </div>
      </div>
    </div>
  );
}
