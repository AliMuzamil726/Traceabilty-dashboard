/** Typed calls to /api/v1/dashboard. Every section takes the same filter parameters. */

import { api, type QueryValue } from '@/core/api/client';
import type {
  Activity,
  Alerts,
  Distribution,
  Interval,
  MapCollection,
  Metric,
  OfficerOverview,
  Onboarding,
  Overview,
  Pipeline,
  Timeseries,
} from './types';

const BASE = '/v1/dashboard';

export type DashboardParams = Record<string, QueryValue>;

export const dashboardApi = {
  overview: (params: DashboardParams, signal?: AbortSignal) =>
    api.get<Overview>(`${BASE}/overview`, params, signal),
  pipeline: (params: DashboardParams, signal?: AbortSignal) =>
    api.get<Pipeline>(`${BASE}/pipeline`, params, signal),
  timeseries: (params: DashboardParams, metric: Metric, interval?: Interval, signal?: AbortSignal) =>
    api.get<Timeseries>(`${BASE}/timeseries`, { ...params, metric, interval }, signal),
  distribution: (params: DashboardParams, signal?: AbortSignal) =>
    api.get<Distribution>(`${BASE}/distribution`, params, signal),
  alerts: (params: DashboardParams, signal?: AbortSignal) =>
    api.get<Alerts>(`${BASE}/alerts`, params, signal),
  activity: (params: DashboardParams, module?: number, signal?: AbortSignal) =>
    api.get<Activity>(`${BASE}/activity`, { ...params, module }, signal),
  map: (params: DashboardParams, signal?: AbortSignal) =>
    api.get<MapCollection>(`${BASE}/map`, params, signal),
  officers: (params: DashboardParams, signal?: AbortSignal) =>
    api.get<OfficerOverview>(`${BASE}/officers`, params, signal),
  onboarding: (params: DashboardParams, signal?: AbortSignal) =>
    api.get<Onboarding>(`${BASE}/onboarding`, params, signal),
};

export const dashboardKeys = {
  all: ['dashboard'] as const,
  section: (section: string, params: DashboardParams, extra?: unknown) =>
    ['dashboard', section, params, extra ?? null] as const,
};
