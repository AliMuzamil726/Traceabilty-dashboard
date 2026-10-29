/** Typed calls to /api/v1/gate. */

import { api } from '@/core/api/client';
import type {
  Crop,
  GateAcceptInput,
  GateAcceptResult,
  GateEntry,
  GateEntryPage,
  GateStatus,
  GateSummary,
  InboundLoad,
} from './types';

const BASE = '/v1/gate';

export interface GateSiteParams {
  siteId: string;
  crop?: Crop;
}

export interface GateEntryParams extends GateSiteParams {
  /** `decided` selects entries that already have an outcome (accepted or rejected). */
  status?: GateStatus | 'decided';
  limit?: number;
}

export const gateApi = {
  summary: (params: GateSiteParams, signal?: AbortSignal) =>
    api.get<GateSummary>(`${BASE}/summary`, { site_id: params.siteId, crop: params.crop }, signal),
  inbound: (params: GateSiteParams, signal?: AbortSignal) =>
    api.get<InboundLoad[]>(`${BASE}/inbound`, { site_id: params.siteId, crop: params.crop }, signal),
  entries: (params: GateEntryParams, signal?: AbortSignal) =>
    api.get<GateEntryPage>(
      `${BASE}/entries`,
      { site_id: params.siteId, crop: params.crop, status: params.status, limit: params.limit },
      signal,
    ),
  arrive: (deliveryId: string) =>
    api.post<GateEntry>(`${BASE}/entries`, { delivery_id: deliveryId }),
  accept: (entryId: string, body: GateAcceptInput) =>
    api.post<GateAcceptResult>(`${BASE}/entries/${entryId}/accept`, body),
  reject: (entryId: string, reason: string) =>
    api.post<GateEntry>(`${BASE}/entries/${entryId}/reject`, { rejection_reason: reason }),
};

export const gateKeys = {
  all: ['gate'] as const,
  summary: (params: GateSiteParams) => ['gate', 'summary', params] as const,
  inbound: (params: GateSiteParams) => ['gate', 'inbound', params] as const,
  entries: (params: GateEntryParams) => ['gate', 'entries', params] as const,
};
