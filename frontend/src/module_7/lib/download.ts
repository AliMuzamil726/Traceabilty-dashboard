/** Fetch a binary from the API with the officer header, and save or show it. */

import { buildUrl, OFFICER_HEADER } from '@/core/api/client';
import { ApiError, isErrorBody } from '@/core/api/errors';
import { useOfficerStore } from '@/core/store/officerStore';

export async function fetchBlob(path: string, body?: unknown): Promise<{ blob: Blob; filename: string | null }> {
  const officerId = useOfficerStore.getState().officerId;
  const headers: Record<string, string> = {};
  if (officerId) headers[OFFICER_HEADER] = officerId;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(buildUrl(path), { method: body === undefined ? 'GET' : 'POST', headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    let data: unknown = null;
    try { data = await res.json(); } catch { /* not JSON */ }
    if (isErrorBody(data)) throw new ApiError(res.status, data.error);
    throw new ApiError(res.status, { code: 'http_error', message: `Request failed with status ${res.status}.`, details: null });
  }
  const filename = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? null;
  return { blob: await res.blob(), filename };
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function download(path: string, fallbackName: string, body?: unknown): Promise<void> {
  const { blob, filename } = await fetchBlob(path, body);
  saveBlob(blob, filename ?? fallbackName);
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
