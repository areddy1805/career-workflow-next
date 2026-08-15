import { fetchApi } from './base';

export async function fetchAuditPipeline(): Promise<any> {
  return fetchApi('/audit/pipeline');
}

export async function fetchAuditFilters(): Promise<any> {
  return fetchApi('/audit/filters');
}

export async function fetchAuditRanking(): Promise<any> {
  return fetchApi('/audit/ranking');
}

export async function fetchAuditSystem(): Promise<any> {
  return fetchApi('/audit/system');
}

export async function fetchAuditExplain(jobId: string): Promise<any> {
  return fetchApi(`/audit/explain?id=${jobId}`);
}
