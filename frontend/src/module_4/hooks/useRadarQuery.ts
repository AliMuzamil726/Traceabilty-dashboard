import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { radarApi, radarKeys, type RadarParams } from '../api/client';

export const REFRESH_MS = 60_000;
export const PAGE_SIZE = 25;

/** Table rows plus bucket counts, KPIs and filter options, refreshed every minute. */
export function useRadarFields(params: RadarParams, sort: string, page: number) {
  const query = { ...params, sort, page, page_size: PAGE_SIZE };
  return useQuery({
    queryKey: radarKeys.fields(query),
    queryFn: ({ signal }) => radarApi.fields(query, signal),
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
  });
}

export function useRadarMap(params: RadarParams, enabled: boolean) {
  return useQuery({
    queryKey: radarKeys.map(params),
    queryFn: ({ signal }) => radarApi.map(params, signal),
    enabled,
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
  });
}

export function useRadarCalendar(params: RadarParams, month: string, enabled: boolean) {
  return useQuery({
    queryKey: radarKeys.calendar(params, month),
    queryFn: ({ signal }) => radarApi.calendar(params, month, signal),
    enabled,
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
  });
}
