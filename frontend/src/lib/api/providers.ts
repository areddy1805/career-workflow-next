import { fetchApi } from './base';

export async function fetchProviders(): Promise<any> {
  return fetchApi('/providers');
}
