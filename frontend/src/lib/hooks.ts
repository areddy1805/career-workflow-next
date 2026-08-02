import { useQuery } from '@tanstack/react-query';
import * as api from './api';
import type { OpportunityListParams } from '@/lib/types/copilot';

// --- Dashboard ---
export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: api.fetchDashboard,
    refetchInterval: 5000,
  });
}

export function useCopilotHealth() {
  return useQuery({
    queryKey: ['copilot', 'health'],
    queryFn: api.fetchCopilotHealth,
    staleTime: 60_000,
    retry: false,
  });
}

export function useViewModel() {
  return useQuery({
    queryKey: ['viewmodel'],
    queryFn: api.fetchViewModel,
    refetchInterval: 1000, // 1s polling
  });
}

// --- Jobs ---
export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: api.fetchJobs,
  });
}

export function useJobDetails(jobId: string) {
  return useQuery({
    queryKey: ['jobs', jobId],
    queryFn: () => api.fetchJobDetails(jobId),
    enabled: !!jobId,
  });
}

// --- Ledger ---
export function useLedgerSearch(params: { query?: string; provider?: string; status?: string; limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: ['ledger', 'search', params],
    queryFn: () => api.fetchLedgerSearch(params),
  });
}

export function useLedgerStats() {
  return useQuery({
    queryKey: ['ledger', 'stats'],
    queryFn: api.fetchLedgerStats,
    refetchInterval: 10000,
  });
}

export function useLedgerJob(fingerprint: string) {
  return useQuery({
    queryKey: ['ledger', 'job', fingerprint],
    queryFn: () => api.fetchLedgerJob(fingerprint),
    enabled: !!fingerprint,
  });
}

// --- Runs ---
export function useRuns() {
  return useQuery({
    queryKey: ['runs'],
    queryFn: api.fetchRuns,
  });
}

export function useRunDetails(runId: string) {
  return useQuery({
    queryKey: ['runs', runId],
    queryFn: () => api.fetchRunDetails(runId),
    enabled: !!runId,
  });
}

export function useArtifacts() {
  return useQuery({
    queryKey: ['artifacts'],
    queryFn: api.fetchArtifacts,
  });
}

export function useRunArtifacts(runId: string) {
  return useQuery({
    queryKey: ['runs', runId, 'artifacts'],
    queryFn: () => api.fetchRunArtifactsList(runId),
    enabled: !!runId,
  });
}

export function useRunArtifactContent(runId: string, fileName: string) {
  return useQuery({
    queryKey: ['runs', runId, 'artifacts', fileName],
    queryFn: () => api.fetchRunArtifactContent(runId, fileName),
    enabled: !!runId && !!fileName,
  });
}

// --- Pipeline ---
export function usePipelineState() {
  return useQuery({
    queryKey: ['pipeline', 'state'],
    queryFn: api.fetchPipelineState,
    refetchInterval: 3000,
  });
}

// --- Metrics ---
export function useMetrics() {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: api.fetchMetrics,
    refetchInterval: 5000,
  });
}

// --- Applications / Queues ---
export function useManualReviewQueue() {
  return useQuery({
    queryKey: ['queue', 'manual-review'],
    queryFn: api.fetchManualReviewQueue,
    refetchInterval: 15000,
  });
}

export function useExternalApplyQueue() {
  return useQuery({
    queryKey: ['queue', 'external-apply'],
    queryFn: api.fetchExternalApplyQueue,
    refetchInterval: 15000,
  });
}

export function useOtherActionQueue() {
  return useQuery({
    queryKey: ['queue', 'other-action'],
    queryFn: api.fetchOtherActionQueue,
    refetchInterval: 15000,
  });
}

// --- Audit ---
export function useAuditPipeline() {
  return useQuery({ queryKey: ['audit', 'pipeline'], queryFn: api.fetchAuditPipeline });
}
export function useAuditFilters() {
  return useQuery({ queryKey: ['audit', 'filters'], queryFn: api.fetchAuditFilters });
}
export function useAuditRanking() {
  return useQuery({ queryKey: ['audit', 'ranking'], queryFn: api.fetchAuditRanking });
}
export function useAuditSystem() {
  return useQuery({ queryKey: ['audit', 'system'], queryFn: api.fetchAuditSystem });
}

// --- Logs ---
export function useLogsPipeline() {
  return useQuery({ queryKey: ['logs', 'pipeline'], queryFn: api.fetchLogsPipeline, refetchInterval: 5000 });
}
export function useLogsRuntime() {
  return useQuery({ queryKey: ['logs', 'runtime'], queryFn: api.fetchLogsRuntime, refetchInterval: 5000 });
}
export function useLogsEventbus() {
  return useQuery({ queryKey: ['logs', 'eventbus'], queryFn: api.fetchLogsEventbus, refetchInterval: 5000 });
}
export function useLogsErrors() {
  return useQuery({ queryKey: ['logs', 'errors'], queryFn: api.fetchLogsErrors, refetchInterval: 5000 });
}
export function useLogsWarnings() {
  return useQuery({ queryKey: ['logs', 'warnings'], queryFn: api.fetchLogsWarnings, refetchInterval: 5000 });
}
export function useLogsLedger() {
  return useQuery({ queryKey: ['logs', 'ledger'], queryFn: api.fetchLogsLedger, refetchInterval: 5000 });
}

// --- Providers ---
export function useProviders() {
  return useQuery({
    queryKey: ['providers'],
    queryFn: api.fetchProviders,
    refetchInterval: 10000,
  });
}

// --- System ---
export function useSystem() {
  return useQuery({
    queryKey: ['system'],
    queryFn: api.fetchSystem,
    refetchInterval: 5000,
  });
}

// --- Developer ---
export function useDeveloper() {
  return useQuery({
    queryKey: ['developer'],
    queryFn: api.fetchDeveloper,
    refetchInterval: 5000,
  });
}

// --- Config ---
export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: api.fetchSettings,
  });
}

// --- Intelligence ---
export function useIntelligence() {
  return useQuery({
    queryKey: ['search-intelligence'],
    queryFn: api.fetchSearchIntelligence,
  });
}

// ─── Copilot (PH6 surfaces; docs/application_copilot/07_UI.md §5) ──────────

export function useCopilotOpportunities(params: OpportunityListParams = {}) {
  return useQuery({
    queryKey: ['copilot', 'opportunities', params],
    queryFn: () => api.fetchCopilotOpportunities(params),
    refetchInterval: 30_000, // inbox poll (07_UI §5)
  });
}

export function useCopilotOpportunity(id: string) {
  return useQuery({
    queryKey: ['copilot', 'opportunity', id],
    queryFn: () => api.fetchCopilotOpportunity(id),
    enabled: !!id,
  });
}

export function useBrief(opportunityId: string) {
  return useQuery({
    queryKey: ['copilot', 'brief', opportunityId],
    queryFn: () => api.fetchBrief(opportunityId),
    enabled: !!opportunityId,
    staleTime: 60_000,
  });
}

export function useSession(sessionId: string, active = false) {
  return useQuery({
    queryKey: ['copilot', 'session', sessionId],
    queryFn: () => api.fetchSession(sessionId),
    enabled: !!sessionId,
    refetchInterval: active ? 1_000 : false, // 1s poll while active (07_UI §5)
  });
}

export function useSessions(limit = 100) {
  return useQuery({
    queryKey: ['copilot', 'sessions'],
    queryFn: () => api.fetchSessions({ limit }),
  });
}

export function useAnswers(params: { profile_id?: string; status?: string; q?: string } = {}) {
  return useQuery({
    queryKey: ['copilot', 'answers', params],
    queryFn: () => api.fetchAnswers(params),
  });
}

export function useAnalytics() {
  return useQuery({
    queryKey: ['copilot', 'analytics'],
    queryFn: api.fetchAnalytics,
    refetchInterval: 30_000, // 30s poll (07_UI §5)
  });
}
