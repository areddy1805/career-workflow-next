import { fetchApi } from './base';

export async function fetchLogsPipeline(): Promise<any> {
  return fetchApi('/logs/pipeline');
}

export async function fetchLogsRuntime(): Promise<any> {
  return fetchApi('/logs/runtime');
}

export async function fetchLogsEventbus(): Promise<any> {
  return fetchApi('/logs/eventbus');
}

export async function fetchLogsErrors(): Promise<any> {
  return fetchApi('/logs/errors');
}

export async function fetchLogsWarnings(): Promise<any> {
  return fetchApi('/logs/warnings');
}

export async function fetchLogsLedger(): Promise<any> {
  return fetchApi('/logs/ledger');
}

export async function fetchLogsSearch(): Promise<any> {
  return fetchApi('/logs/search');
}
