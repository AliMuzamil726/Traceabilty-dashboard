import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { dashboardApi, dashboardKeys, type DashboardParams } from '../api/client';
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
} from '../api/types';

/**
 * One hook per section, so each one loads, fails and retries on its own: a section
 * that cannot be read shows its own retry and the rest of the page still works.
 *
 * When filters (crop / season / range) change, every section shows loading and
 * refetches — the whole dashboard feels like a complete refresh, not just the
 * Delivered KPI label.
 */
export const REFRESH_INTERVAL_MS = 60_000;

const options = {
  refetchOnWindowFocus: false,
  // Short stale time so a filter change is never served from a long-lived cache.
  staleTime: 0,
  // Do not keep showing the previous range's numbers while the new range loads.
  placeholderData: undefined,
  gcTime: 30_000,
} as const;

export function useOverview(params: DashboardParams, enabled = true): UseQueryResult<Overview> {
  return useQuery({
    queryKey: dashboardKeys.section('overview', params),
    queryFn: ({ signal }) => dashboardApi.overview(params, signal),
    enabled,
    ...options,
  });
}

export function usePipeline(params: DashboardParams, enabled = true): UseQueryResult<Pipeline> {
  return useQuery({
    queryKey: dashboardKeys.section('pipeline', params),
    queryFn: ({ signal }) => dashboardApi.pipeline(params, signal),
    enabled,
    ...options,
  });
}

export function useTimeseries(
  params: DashboardParams,
  metric: Metric,
  interval?: Interval,
  enabled = true,
): UseQueryResult<Timeseries> {
  return useQuery({
    queryKey: dashboardKeys.section('timeseries', params, [metric, interval ?? null]),
    queryFn: ({ signal }) => dashboardApi.timeseries(params, metric, interval, signal),
    enabled,
    ...options,
  });
}

export function useDistribution(
  params: DashboardParams,
  enabled = true,
): UseQueryResult<Distribution> {
  return useQuery({
    queryKey: dashboardKeys.section('distribution', params),
    queryFn: ({ signal }) => dashboardApi.distribution(params, signal),
    enabled,
    ...options,
  });
}

export function useAlerts(params: DashboardParams, enabled = true): UseQueryResult<Alerts> {
  return useQuery({
    queryKey: dashboardKeys.section('alerts', params),
    queryFn: ({ signal }) => dashboardApi.alerts(params, signal),
    enabled,
    ...options,
  });
}

export function useActivity(
  params: DashboardParams,
  module: number | null,
  enabled = true,
): UseQueryResult<Activity> {
  return useQuery({
    queryKey: dashboardKeys.section('activity', params, module),
    queryFn: ({ signal }) => dashboardApi.activity(params, module ?? undefined, signal),
    enabled,
    ...options,
  });
}

export function useDashboardMap(
  params: DashboardParams,
  enabled = true,
): UseQueryResult<MapCollection> {
  return useQuery({
    queryKey: dashboardKeys.section('map', params),
    queryFn: ({ signal }) => dashboardApi.map(params, signal),
    enabled,
    ...options,
  });
}

/** Administrators only; the server refuses it for an officer, so it is not requested. */
export function useOfficerOverview(
  params: DashboardParams,
  enabled: boolean,
): UseQueryResult<OfficerOverview> {
  return useQuery({
    queryKey: dashboardKeys.section('officers', params),
    queryFn: ({ signal }) => dashboardApi.officers(params, signal),
    enabled,
    ...options,
  });
}

export function useOnboarding(params: DashboardParams, enabled = true): UseQueryResult<Onboarding> {
  return useQuery({
    queryKey: dashboardKeys.section('onboarding', params),
    queryFn: ({ signal }) => dashboardApi.onboarding(params, signal),
    enabled,
    ...options,
  });
}
