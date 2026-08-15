import { fetchApi } from './base';

export async function fetchSystem(): Promise<any> {
  return fetchApi('/runtime');
}

export async function fetchDeveloper(): Promise<any> {
  return fetchApi('/developer');
}
