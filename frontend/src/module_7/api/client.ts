/** Typed calls to /api/v1/qr. */

import { api } from '@/core/api/client';
import type { BaleRow, Crop, InternalTrace, LotOverview, LotsResponse, PublicTrace, Resolved, ScanSummary } from './types';

const BASE = '/v1/qr';

export const qrApi = {
  lots: (params: { crop?: Crop; site_id?: string }, signal?: AbortSignal) => api.get<LotsResponse>(`${BASE}/lots`, { ...params }, signal),
  overview: (heapId: string, signal?: AbortSignal) => api.get<LotOverview>(`${BASE}/lots/${heapId}/overview`, undefined, signal),
  bales: (heapId: string, signal?: AbortSignal) => api.get<BaleRow[]>(`${BASE}/bales`, { heap_id: heapId }, signal),
  publicTrace: (token: string, signal?: AbortSignal) =>
    api.get<PublicTrace>(`${BASE}/public/${encodeURIComponent(token)}`, undefined, signal),
  traceBale: (serial: string, signal?: AbortSignal) => api.get<InternalTrace>(`${BASE}/trace/bale/${serial}`, undefined, signal),
  traceHeap: (heapId: string, signal?: AbortSignal) => api.get<InternalTrace>(`${BASE}/trace/heap/${heapId}`, undefined, signal),
  resolve: (q: string) => api.get<Resolved>(`${BASE}/resolve`, { q }),
  scanSummary: (heapId?: string, signal?: AbortSignal) => api.get<ScanSummary>(`${BASE}/scans/summary`, { heap_id: heapId }, signal),
  revoke: (token: string, reason: string) => api.post<{ token: string; status: string }>(`${BASE}/tokens/${token}/revoke`, { reason }),
  regenerate: (serial: string, reason: string) =>
    api.post<{ token: string; status: string; bale_serial: string; trace_url: string }>(`${BASE}/bales/${serial}/regenerate`, { reason }),
  pngPath: (token: string, size = 10) => `${BASE}/tokens/${token}/image.png?size=${size}`,
  svgPath: (token: string) => `${BASE}/tokens/${token}/image.svg`,
  labelsPath: `${BASE}/labels`,
  zipPath: `${BASE}/images.zip`,
  labelPngPath: (serial: string) => `${BASE}/bales/${serial}/label.png`,
};

export const qrKeys = {
  all: ['qr'] as const,
  lots: (params: object) => ['qr', 'lots', params] as const,
  overview: (heapId: string) => ['qr', 'overview', heapId] as const,
  bales: (heapId: string) => ['qr', 'bales', heapId] as const,
  trace: (kind: string, id: string) => ['qr', 'trace', kind, id] as const,
  publicTrace: (token: string) => ['qr', 'public', token] as const,
};
