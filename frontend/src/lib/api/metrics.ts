import { fetchApi } from './base';

export async function fetchMetrics(): Promise<any> {
  // Can just reuse runtime or a specific metrics endpoint if needed.
  // For now, runtime has most metrics.
  return fetchApi('/runtime');
}
