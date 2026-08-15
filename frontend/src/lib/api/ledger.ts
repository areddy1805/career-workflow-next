import { fetchApi } from './base';

export async function fetchLedgerSearch(params: { query?: string; provider?: string; status?: string; limit?: number; offset?: number } = {}): Promise<any> {
  const qs = new URLSearchParams();
  if (params.query) qs.append('query', params.query);
  if (params.provider) qs.append('provider', params.provider);
  if (params.status) qs.append('status', params.status);
  if (params.limit) qs.append('limit', params.limit.toString());
  if (params.offset) qs.append('offset', params.offset.toString());
  
  return fetchApi(`/ledger/search?${qs.toString()}`);
}

export async function fetchLedgerStats(): Promise<any> {
  return fetchApi('/ledger/stats');
}

export async function fetchLedgerJob(fingerprint: string): Promise<any> {
  return fetchApi(`/ledger/job/${fingerprint}`);
}
