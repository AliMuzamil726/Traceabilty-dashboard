import { useOfficerStore } from '@/core/store/officerStore';
import { ApiError, isErrorBody } from './errors';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '');
export const OFFICER_HEADER = 'X-Officer-Id';

export type QueryValue = string | number | boolean | null | undefined;

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  query?: Record<string, QueryValue>;
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const clean = path.startsWith('/') ? path : `/${path}`;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const qs = params.toString();
  return `${API_BASE_URL}${clean}${qs ? `?${qs}` : ''}`;
}

/**
 * Typed fetch wrapper. Paths are relative to the API base, e.g. `/v1/officers`.
 * Sends the acting officer on every request and turns every failure into ApiError.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, body, signal, headers = {} } = options;
  const officerId = useOfficerStore.getState().officerId;
  const finalHeaders: Record<string, string> = { Accept: 'application/json', ...headers };
  if (officerId) finalHeaders[OFFICER_HEADER] = officerId;
  if (body !== undefined && !(body instanceof FormData)) finalHeaders['Content-Type'] = 'application/json';

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: finalHeaders,
      signal,
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
    throw new ApiError(0, {
      code: 'network_error',
      message: 'The server could not be reached. Check that the backend is running.',
      details: null,
    });
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const data: unknown = text ? safeJson(text) : null;

  if (!response.ok) {
    if (isErrorBody(data)) {
      // A stale officer id (e.g. after a database reset): forget it and fall back.
      if (data.error.code === 'officer_not_found' && officerId) {
        useOfficerStore.getState().clearOfficer();
      }
      throw new ApiError(response.status, data.error);
    }
    throw new ApiError(response.status, {
      code: 'http_error',
      message: `Request failed with status ${response.status}.`,
      details: null,
    });
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export const api = {
  get: <T>(path: string, query?: Record<string, QueryValue>, signal?: AbortSignal) =>
    apiRequest<T>(path, { query, signal }),
  post: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: 'POST', body }),
  put: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: 'PATCH', body }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: 'DELETE' }),
};
