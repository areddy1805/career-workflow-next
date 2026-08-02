import { fetchApi } from './base';

export async function fetchRuns(): Promise<any> {
  return fetchApi('/runs');
}

export async function fetchRunDetails(runId: string): Promise<any> {
  return fetchApi(`/runs/${runId}`);
}

export async function fetchArtifacts(): Promise<any> {
  return fetchApi('/artifacts');
}

export async function fetchRunArtifactsList(runId: string): Promise<any> {
  return fetchApi(`/runs/${runId}/artifacts`);
}

export async function fetchRunArtifactContent(runId: string, fileName: string): Promise<any> {
  return fetchApi(`/runs/${runId}/artifacts/${fileName}`);
}
