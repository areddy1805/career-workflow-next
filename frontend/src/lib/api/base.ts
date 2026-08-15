const API_BASE = '/api';

// D-033: never wait forever on a stalled backend (e.g. a hung browser
// launch). A timed-out request surfaces as an explicit error instead of an
// infinite spinner.
const DEFAULT_TIMEOUT_MS = 90_000;

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      let message = 'API request failed';
      try {
        const errorData = await response.json();
        // Copilot endpoints use the {ok, error: {message, type}} envelope; the
        // rest of the API uses {detail} or {message}. Prefer the copilot
        // envelope's nested message, then the standard shapes.
        message =
          errorData.error?.message || errorData.detail || errorData.message || message;
      } catch {
        message = response.statusText;
      }
      throw new Error(message);
    }

    return response.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error(`Request timed out after ${DEFAULT_TIMEOUT_MS / 1000}s`);
    }
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
}
