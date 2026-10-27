/** Typed calls to /api/v1/radar. Every read takes the same filter parameters. */

import { api, apiRequest, buildUrl, OFFICER_HEADER, type QueryValue } from '@/core/api/client';
import { ApiError, isErrorBody } from '@/core/api/errors';
import type { Page } from '@/core/api/types';
import { useOfficerStore } from '@/core/store/officerStore';
import type { CalendarData, Crop, FieldsPage, MapCollection, PickupRequest, PickupResult } from './types';

const BASE = '/v1/radar';

export type RadarParams = Record<string, QueryValue>;

export const radarApi = {
  fields: (params: RadarParams, signal?: AbortSignal) => api.get<FieldsPage>(`${BASE}/fields`, params, signal),
  map: (params: RadarParams, signal?: AbortSignal) => api.get<MapCollection>(`${BASE}/map`, params, signal),
  calendar: (params: RadarParams, month: string, signal?: AbortSignal) =>
    api.get<CalendarData>(`${BASE}/calendar`, { ...params, month }, signal),
  requests: (params: { crop: Crop; season_year: number; status?: string; scope?: string; page?: number }, signal?: AbortSignal) =>
    api.get<Page<PickupRequest>>(`${BASE}/pickup-requests`, { ...params, page_size: 50 }, signal),
  requestPickup: (body: { crop: Crop; season_year: number; field_ids: string[]; preferred_date?: string | null; note?: string | null }) =>
    api.post<PickupResult>(`${BASE}/pickup-requests`, body),
  cancel: (requestId: string, reason: string) =>
    apiRequest<PickupRequest>(`${BASE}/pickup-requests/${requestId}/cancel`, { method: 'POST', body: { reason } }),

  /** Download the CSV through fetch so the officer header goes with it. */
  exportCsv: async (params: RadarParams): Promise<{ blob: Blob; filename: string }> => {
    const officerId = useOfficerStore.getState().officerId;
    const res = await fetch(buildUrl(`${BASE}/export.csv`, params), {
      headers: officerId ? { [OFFICER_HEADER]: officerId } : {},
    });
    if (!res.ok) {
      const body: unknown = await res.json().catch(() => null);
      throw new ApiError(res.status, isErrorBody(body) ? body.error : { code: 'http_error', message: 'The export failed.', details: null });
    }
    const disposition = res.headers.get('Content-Disposition') ?? '';
    const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'radar.csv';
    return { blob: await res.blob(), filename };
  },
};

export const radarKeys = {
  all: ['radar'] as const,
  fields: (params: RadarParams) => ['radar', 'fields', params] as const,
  map: (params: RadarParams) => ['radar', 'map', params] as const,
  calendar: (params: RadarParams, month: string) => ['radar', 'calendar', params, month] as const,
  requests: (params: object) => ['radar', 'requests', params] as const,
};
