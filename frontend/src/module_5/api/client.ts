/** Typed calls to /api/v1/deliveries. */

import { api, buildUrl, OFFICER_HEADER, type QueryValue } from '@/core/api/client';
import { ApiError, isErrorBody } from '@/core/api/errors';
import { useOfficerStore } from '@/core/store/officerStore';
import type {
  DeliveryDetail,
  DeliveryPage,
  InboxItem,
  ScheduleInput,
  Skipped,
  Stats,
  TransitionResult,
  Delivery,
} from './types';

const BASE = '/v1/deliveries';
export type DeliveryParams = Record<string, QueryValue>;

export const deliveriesApi = {
  inbox: (params: DeliveryParams, signal?: AbortSignal) => api.get<InboxItem[]>(`${BASE}/inbox`, params, signal),
  schedule: (body: ScheduleInput) => api.post<{ created: Delivery[]; skipped: Skipped[] }>(`${BASE}/schedule`, body),
  list: (params: DeliveryParams, signal?: AbortSignal) => api.get<DeliveryPage>(BASE, params, signal),
  get: (id: string, signal?: AbortSignal) => api.get<DeliveryDetail>(`${BASE}/${id}`, undefined, signal),
  stats: (params: DeliveryParams, signal?: AbortSignal) => api.get<Stats>(`${BASE}/stats`, params, signal),
  update: (id: string, body: Partial<ScheduleInput>) => api.put<DeliveryDetail>(`${BASE}/${id}`, body),
  dispatch: (id: string, body: { field_weight_kg?: number | null; note?: string | null }) =>
    api.post<TransitionResult>(`${BASE}/${id}/dispatch`, body),
  receive: (id: string, body: { weighbridge_weight_kg: number; moisture_pct: number; note?: string | null }) =>
    api.post<TransitionResult>(`${BASE}/${id}/receive`, body),
  cancel: (id: string, reason: string) => api.post<DeliveryDetail>(`${BASE}/${id}/cancel`, { reason }),
  correct: (id: string, body: { reason: string; weighbridge_weight_kg?: number | null; moisture_pct?: number | null; field_weight_kg?: number | null }) =>
    api.post<TransitionResult>(`${BASE}/${id}/correct`, body),

  /** Fetch a file through the officer header and hand it to the browser. */
  download: async (path: string, params: DeliveryParams = {}): Promise<void> => {
    const officerId = useOfficerStore.getState().officerId;
    const res = await fetch(buildUrl(`${BASE}${path}`, params), { headers: officerId ? { [OFFICER_HEADER]: officerId } : {} });
    if (!res.ok) {
      const body: unknown = await res.json().catch(() => null);
      throw new ApiError(res.status, isErrorBody(body) ? body.error : { code: 'http_error', message: 'The download failed.', details: null });
    }
    const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'download';
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};

export const deliveryKeys = {
  all: ['deliveries'] as const,
  inbox: (params: object) => ['deliveries', 'inbox', params] as const,
  list: (params: object) => ['deliveries', 'list', params] as const,
  detail: (id: string) => ['deliveries', 'detail', id] as const,
  stats: (params: object) => ['deliveries', 'stats', params] as const,
};
