import { fetchApi } from './base';

// ─── Runtime state (DESIGN.md §4, §6) ────────────────────────────────────────
// /api/runtime — the truthful process-state source for the shell status chip
// and the Overview operating-state bar. Scheduler statuses (backend):
// RUNNING | IDLE | STOPPED | STALE | ORPHANED. latest_run.status NONE when no
// run is on record.

export interface SchedulerRuntime {
  status?: string;
  pid?: number | null;
  is_alive?: boolean;
  [key: string]: unknown;
}

export interface PipelineRuntime {
  status?: string;
  pid?: number | null;
  is_alive?: boolean;
  [key: string]: unknown;
}

export interface LatestRunRuntime {
  status?: string;
  id?: string | null;
  completed_at?: string | null;
  acquisition_metrics?: Record<string, unknown>;
  classification_metrics?: Record<string, unknown>;
  selection_metrics?: Record<string, unknown>;
  application_metrics?: Record<string, unknown>;
  errors?: unknown[];
}

export interface RuntimeInfo {
  scheduler?: SchedulerRuntime;
  pipeline?: PipelineRuntime;
  ui?: Record<string, unknown>;
  latest_run?: LatestRunRuntime;
}

export async function fetchRuntime(): Promise<RuntimeInfo> {
  return fetchApi<RuntimeInfo>('/runtime');
}
