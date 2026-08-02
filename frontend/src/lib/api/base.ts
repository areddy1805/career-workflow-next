const API_BASE = '/api';

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const response = await fetch(url, {
    ...options,
    headers,
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
}
