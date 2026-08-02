import { fetchApi } from './base';

export async function fetchSettings(): Promise<any> {
  return fetchApi('/settings');
}
