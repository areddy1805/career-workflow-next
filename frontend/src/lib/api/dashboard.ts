import { fetchApi } from './base';

export async function fetchDashboard(): Promise<any> {
  return fetchApi('/dashboard');
}

export async function fetchSearchIntelligence(): Promise<any> {
  return fetchApi('/search-intelligence');
}

export async function fetchViewModel(): Promise<any> {
  return fetchApi('/api/v1/viewmodel');
}
