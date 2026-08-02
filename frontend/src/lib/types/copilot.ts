/**
 * Copilot API types (mirrors docs/application_copilot/02_ARCHITECTURE.md §7.9).
 */

export type CopilotSubsystemStatus = 'ok' | 'error' | 'unmigrated' | 'missing';

export interface CopilotHealthData {
  status: 'ok' | 'degraded';
  version: string;
  subsystems: Record<string, CopilotSubsystemStatus>;
}

/** Response envelope: { ok, data?, error? } (§7.9). */
export interface CopilotHealthResponse {
  ok: boolean;
  data?: CopilotHealthData;
  error?: { message: string };
}

// ─── Opportunities (CP-1-13 / §7.9) ────────────────────────────────────────

export interface CopilotOpportunity {
  opportunity_id: string;
  source: string;
  title: string;
  company: string;
  provider_id: string;
  provider_job_id: string;
  source_url: string | null;
  canonical_url: string | null;
  seniority: string | null;
  employment_type: string | null;
  work_mode: string | null;
  experience_required: string | null;
  role_family: string | null;
  company_domain: string | null;
  ats_type: string | null;
  careers_url: string | null;
  comp_min: number | null;
  comp_max: number | null;
  currency: string | null;
  comp_notes: string | null;
  equity: string | null;
  bonus: string | null;
  city: string | null;
  region: string | null;
  country: string | null;
  remote: boolean | null;
  relocation_required: boolean | null;
  apply_url: string | null;
  application_strategy: string;
  status_view: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunityListResponse {
  ok: boolean;
  data: CopilotOpportunity[];
}

export interface OpportunityListParams {
  source?: string;
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

// ─── Brief (CP-2-07 / §7.9) ────────────────────────────────────────────────

export interface BriefSection {
  key: string;
  title: string;
  content: string;
  provenance: string;
  llm_augmented: boolean;
}

export interface BriefResponse {
  ok: boolean;
  data: {
    opportunity_id: string;
    generated_at: string;
    model_used: string | null;
    sections_version: string | null;
    sections: BriefSection[];
    // The backend emits verdict as a plain string ("APPLY"|"CONSIDER"|"SKIP")
    // plus verdict_reason; accept the object shape too for compatibility.
    verdict?: string | { label: string; class: string } | null;
    verdict_reason?: string | null;
  };
}

/** Normalize the brief verdict to a plain label string (or null). */
export function verdictLabel(verdict: BriefResponse['data']['verdict']): string | null {
  if (typeof verdict === 'string') return verdict;
  return verdict?.label ?? null;
}

// ─── Sessions (CP-4-05 / §7.9) ─────────────────────────────────────────────

export interface CopilotSession {
  session_id: string;
  opportunity_id: string;
  state: string;
  profile_id: string;
  resume_id: string | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  outcome: string | null;
  outcome_at: string | null;
  answers_snapshot_json: string | null;
  brief_snapshot_json: string | null;
}

export interface SessionEvent {
  session_id: string;
  seq: number;
  event_type: string;
  occurred_at: string;
  payload_json: string;
}

export interface SessionDetailResponse {
  ok: boolean;
  data: {
    session: CopilotSession;
    events: SessionEvent[];
  };
}

// ─── Answers (CP-3-06 / §7.9) ──────────────────────────────────────────────

export interface StoredAnswer {
  question_fp: string;
  profile_id: string;
  canonical_label: string | null;
  category: string | null;
  source: string;
  semantic_answer: unknown;
  serialized_answer: unknown;
  confidence: number | null;
  status: string;
  reason: string | null;
  use_count: number;
  last_used_at: string | null;
  outcome_quality: number | null;
}

export interface AnswerListResponse {
  ok: boolean;
  data: StoredAnswer[];
}

// ─── Analytics (CP-8-03 / §7.9) ─────────────────────────────────────────────

export interface FunnelStageCounts {
  ingested: number;
  briefed: number;
  viewed: number;
  applied: number;
  submitted: number;
  shortlisted: number;
  interview: number;
  offer: number;
}

/** Per-stage conversion = stage[n] / stage[n-1]; null when the previous stage is 0. */
export interface FunnelConversions {
  briefed: number | null;
  viewed: number | null;
  applied: number | null;
  submitted: number | null;
  shortlisted: number | null;
  interview: number | null;
  offer: number | null;
}

export interface FunnelData {
  stages: FunnelStageCounts;
  conversions: FunnelConversions;
}

export interface EffortSavedData {
  manual_estimate_min: number;
  assisted_estimate_min: number;
  saved_min: number;
  saved_pct: number;
  median_assisted_minutes: number;
}

export interface AnswerHealthData {
  total: number;
  by_source: Record<string, number>;
  auto_resolve_rate: number;
  correction_rate: number;
}

export interface LlmTrendPoint {
  date: string;
  count: number;
}

export interface CalibrationPair {
  opportunity_id: string;
  predicted: number;
  actual: number;
}

export interface CalibrationData {
  pairs: CalibrationPair[];
  mean_abs_error: number | null;
  sample_count: number;
}

export interface AnalyticsData {
  funnel: FunnelData;
  effort: EffortSavedData;
  answer_health: AnswerHealthData;
  llm_trend: LlmTrendPoint[];
  calibration: CalibrationData;
  success_metrics: Record<string, { value: unknown; note?: string }>;
}

export interface AnalyticsResponse {
  ok: boolean;
  data: AnalyticsData;
}
