/**
 * Copilot API client (docs/application_copilot/02_ARCHITECTURE.md §7.9).
 * Endpoint modules + hooks for the PH6 surfaces.
 */

import { fetchApi } from './base';
import type {
  AnswerListResponse,
  BriefResponse,
  CopilotHealthResponse,
  CopilotOpportunity,
  CopilotSession,
  OpportunityListParams,
  OpportunityListResponse,
  SessionDetailResponse,
  StoredAnswer,
} from '@/lib/types/copilot';

// ─── Health ────────────────────────────────────────────────────────────────

export async function fetchCopilotHealth(): Promise<CopilotHealthResponse> {
  return fetchApi<CopilotHealthResponse>('/copilot/health');
}

// ─── Opportunities ─────────────────────────────────────────────────────────

export async function fetchCopilotOpportunities(
  params: OpportunityListParams = {},
): Promise<OpportunityListResponse> {
  const query = new URLSearchParams();
  if (params.source) query.set('source', params.source);
  if (params.status) query.set('status', params.status);
  if (params.q) query.set('q', params.q);
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  return fetchApi<OpportunityListResponse>(
    `/copilot/opportunities${qs ? `?${qs}` : ''}`,
  );
}

export async function fetchCopilotOpportunity(id: string): Promise<CopilotOpportunity> {
  const res = await fetchApi<{ ok: boolean; data: CopilotOpportunity }>(
    `/copilot/opportunities/${id}`,
  );
  return res.data;
}

// ─── Brief ─────────────────────────────────────────────────────────────────

export async function fetchBrief(opportunityId: string): Promise<BriefResponse['data']> {
  const res = await fetchApi<BriefResponse>(
    `/copilot/opportunities/${opportunityId}/brief`,
  );
  return res.data;
}

// ─── Sessions ──────────────────────────────────────────────────────────────

export interface SessionCreateRequest {
  opportunity_id: string;
  profile_id?: string;
  resume_id?: string;
}

export async function createSession(request: SessionCreateRequest) {
  return fetchApi<{ ok: boolean; data: CopilotSession }>('/copilot/sessions', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function fetchSession(sessionId: string): Promise<SessionDetailResponse['data']> {
  const res = await fetchApi<SessionDetailResponse>(`/copilot/sessions/${sessionId}`);
  return res.data;
}

export async function fetchSessions(params: { limit?: number; offset?: number } = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  return fetchApi<{ ok: boolean; data: CopilotSession[] }>(
    `/copilot/sessions${qs ? `?${qs}` : ''}`,
  );
}

export async function advanceSession(sessionId: string, event: string, payload: Record<string, unknown> = {}) {
  return fetchApi<{ ok: boolean; data: CopilotSession }>(
    `/copilot/sessions/${sessionId}/advance`,
    {
      method: 'POST',
      body: JSON.stringify({ event, payload }),
    },
  );
}

export async function abortSession(sessionId: string) {
  return fetchApi<{ ok: boolean; data: CopilotSession }>(
    `/copilot/sessions/${sessionId}/abort`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

// ─── Answers ───────────────────────────────────────────────────────────────

export async function fetchAnswers(params: {
  profile_id?: string;
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<StoredAnswer[]> {
  const query = new URLSearchParams();
  if (params.profile_id) query.set('profile_id', params.profile_id);
  if (params.status) query.set('status', params.status);
  if (params.q) query.set('q', params.q);
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  const res = await fetchApi<AnswerListResponse>(
    `/copilot/answers${qs ? `?${qs}` : ''}`,
  );
  return res.data;
}

export async function updateAnswer(fp: string, payload: Record<string, unknown>) {
  return fetchApi(`/copilot/answers/${fp}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function confirmAnswer(payload: {
  question_fp: string;
  profile_id?: string;
  answer: unknown;
  actor?: string;
}) {
  return fetchApi('/copilot/answers/confirm', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function lockAnswer(payload: { question_fp: string; profile_id?: string; locked?: boolean }) {
  return fetchApi('/copilot/answers/lock', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function switchProfile(profileId: string) {
  return fetchApi('/copilot/profiles/switch', {
    method: 'POST',
    body: JSON.stringify({ profile_id: profileId }),
  });
}

// ─── Browser Assistant (CP-5-08 / §7.9) ────────────────────────────────────

export interface BrowserOpenRequest {
  opportunity_id: string;
  session_id: string;
  profile_id?: string;
  url?: string;
}

export async function browserOpen(request: BrowserOpenRequest) {
  return fetchApi<{ ok: boolean; data: BrowserSession }>('/copilot/browser/open', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function browserForm(sessionId?: string) {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
  return fetchApi<{ ok: boolean; data: FormModel }>(`/copilot/browser/form${qs}`);
}

export async function browserFill(fieldId: string, sessionId?: string) {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
  return fetchApi<{ ok: boolean; data: FieldFill }>(
    `/copilot/browser/fill/${encodeURIComponent(fieldId)}${qs}`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

export async function browserCheckpoint(sessionId?: string) {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
  return fetchApi<{ ok: boolean; data: Checkpoint | null }>(
    `/copilot/browser/checkpoint${qs}`,
  );
}

export async function browserConfirm(checkpointId: string, action = 'confirm', sessionId?: string) {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
  return fetchApi<{ ok: boolean; data: BrowserSession }>(
    `/copilot/browser/confirm${qs}`,
    { method: 'POST', body: JSON.stringify({ checkpoint_id: checkpointId, action }) },
  );
}

export async function browserSubmit(humanGesture: boolean, sessionId?: string) {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
  return fetchApi<{ ok: boolean; data: SubmitResult }>(`/copilot/browser/submit${qs}`, {
    method: 'POST',
    body: JSON.stringify({ human_gesture: humanGesture }),
  });
}

export async function browserGuidance(sessionId?: string) {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
  return fetchApi<{ ok: boolean; data: GuidancePlan }>(`/copilot/browser/guidance${qs}`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export async function browserAbort(reason = 'aborted by user') {
  return fetchApi<{ ok: boolean; data: BrowserSession }>('/copilot/browser/abort', {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

// ─── Browser shapes (§7.6) ─────────────────────────────────────────────────

export interface BrowserSession {
  session_id: string;
  opportunity_id: string;
  url: string;
  state: string;
  page_url: string | null;
  title: string | null;
}

export interface FieldOption {
  value: string;
  label: string;
}

export interface TypedField {
  field_id: string;
  kind: string;
  label: string;
  name: string;
  options: FieldOption[];
  required: boolean;
  page: number;
  confidence: number;
}

export interface FormModel {
  fields: TypedField[];
  pages: number;
  ats_type: string;
  auto_fillable: boolean;
}

export interface FieldFill {
  field_id: string;
  resolution: Record<string, unknown>;
  filled: boolean;
  confidence: number | null;
  source: string;
  reason: string;
}

export interface PendingItem {
  type: string;
  field_id: string;
  reason: string;
}

export interface Checkpoint {
  checkpoint_id: string;
  type: string;
  gates_open: boolean;
  pending: PendingItem[];
  dismissible: boolean;
}

export interface SubmitResult {
  submitted: boolean;
  page_url: string;
  outcome: string;
}

export interface GuidanceStep {
  field_id: string;
  label: string;
  instruction: string;
}

export interface GuidancePlan {
  reason: string;
  steps: GuidanceStep[];
}
