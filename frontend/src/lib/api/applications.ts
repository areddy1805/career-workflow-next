import { fetchApi } from './base';

export async function fetchManualReviewQueue(): Promise<any> {
  return fetchApi('/queues/manual-review');
}

export async function fetchExternalApplyQueue(): Promise<any> {
  return fetchApi('/queues/external-apply');
}

export async function fetchOtherActionQueue(): Promise<any> {
  return fetchApi('/queues/other-action');
}

export async function transitionQueueJob(jobId: string, to_status: string, note?: string): Promise<any> {
  return fetchApi(`/queues/${jobId}/transition`, {
    method: 'POST',
    body: JSON.stringify({ to_status, note }),
  });
}

export async function moveQueueJob(jobId: string, queue: string): Promise<any> {
  return fetchApi(`/queues/${jobId}/move`, {
    method: 'POST',
    body: JSON.stringify({ queue }),
  });
}
