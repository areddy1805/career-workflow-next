import { fetchApi } from './base';

export async function fetchJobs(): Promise<any> {
  return fetchApi('/jobs');
}

export async function fetchJobDetails(jobId: string): Promise<any> {
  return fetchApi(`/jobs/${jobId}`);
}
