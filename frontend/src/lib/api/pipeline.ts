import { fetchApi } from './base';

export async function fetchPipelineState(): Promise<any> {
  return fetchApi('/pipeline/state');
}

export async function launchPipeline(params: { live?: boolean; max_applications?: number; canary?: boolean; force_live?: boolean }): Promise<any> {
  return fetchApi('/pipeline/launch', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}
