/** Typed calls to /api/v1/heaps. */

import { api, apiRequest } from '@/core/api/client';
import type { Crop, HeapDetail, HeapListItem, Skipped } from './types';

const BASE = '/v1/heaps';

export const heapsApi = {
  list: (params: { crop?: Crop; site_id?: string; status?: 'open' | 'closed' }, signal?: AbortSignal) =>
    api.get<HeapListItem[]>(BASE, { ...params }, signal),
  get: (key: string, signal?: AbortSignal) => api.get<HeapDetail>(`${BASE}/${key}`, undefined, signal),
  open: (siteId: string, note?: string) =>
    api.post<{ heap: HeapDetail; warnings: string[] }>(BASE, { site_id: siteId, note: note || null }),
  update: (key: string, body: Partial<Pick<HeapDetail, 'outturn_ratio_pct' | 'bale_unit_kg' | 'shiv_pct' | 'dust_pct' | 'note'>>) =>
    api.put<HeapDetail>(`${BASE}/${key}`, body),
  addDeliveries: (key: string, deliveryIds: string[]) =>
    api.post<{ heap: HeapDetail; added: string[]; skipped: Skipped[] }>(`${BASE}/${key}/deliveries`, { delivery_ids: deliveryIds }),
  removeDelivery: (key: string, deliveryId: string, reason: string) =>
    apiRequest<HeapDetail>(`${BASE}/${key}/deliveries/${deliveryId}`, { method: 'DELETE', query: { reason } }),
  createBales: (key: string, count: number) => api.post<HeapDetail>(`${BASE}/${key}/bales`, { count }),
  voidBale: (serial: string, reason: string) => api.post<unknown>(`${BASE}/bales/${serial}/void`, { reason }),
  close: (key: string, body: { reason?: string | null; with_remainder?: boolean }) =>
    api.post<HeapDetail>(`${BASE}/${key}/close`, body),
  exportCsvUrl: (key: string) => `${BASE}/${key}/export.csv`,
};

export const heapKeys = {
  all: ['heaps'] as const,
  list: (params: object) => ['heaps', 'list', params] as const,
  detail: (key: string) => ['heaps', 'detail', key] as const,
};
