import { useQuery } from '@tanstack/react-query';
import { api } from '@/core/api/client';
import type { CurrentOfficer, Health, MasterList, Officer, Page, Site } from '@/core/api/types';
import { useOfficerStore } from '@/core/store/officerStore';

export const sharedKeys = {
  health: ['health'] as const,
  me: (officerId: string | null) => ['officers', 'me', officerId] as const,
  officers: ['officers', 'all'] as const,
  sites: (crop?: string) => ['sites', crop ?? null] as const,
  master: (key: string, country?: string, crop?: string) =>
    ['master', key, country ?? null, crop ?? null] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: sharedKeys.health,
    queryFn: ({ signal }) => api.get<Health>('/health', undefined, signal),
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useCurrentOfficer() {
  const officerId = useOfficerStore((s) => s.officerId);
  return useQuery({
    queryKey: sharedKeys.me(officerId),
    queryFn: ({ signal }) => api.get<CurrentOfficer>('/v1/officers/me', undefined, signal),
  });
}

export function useOfficers() {
  return useQuery({
    queryKey: sharedKeys.officers,
    queryFn: ({ signal }) =>
      api.get<Page<Officer>>('/v1/officers', { page_size: 200 }, signal),
    staleTime: 5 * 60_000,
  });
}

/** Every dropdown reads its options from here (never hard-coded in React). */
export function useMasterList(listKey: string, scope: { country?: string; crop?: string } = {}) {
  return useQuery({
    queryKey: sharedKeys.master(listKey, scope.country, scope.crop),
    queryFn: ({ signal }) =>
      api.get<MasterList>(`/v1/master/${listKey}`, { country: scope.country, crop: scope.crop }, signal),
    staleTime: 10 * 60_000,
  });
}

/** Delivery sites, optionally for one crop. Shared by Deliveries, Heap and QR Tracing. */
export function useSites(crop?: string) {
  return useQuery({
    queryKey: sharedKeys.sites(crop),
    queryFn: ({ signal }) => api.get<Site[]>('/v1/sites', { crop }, signal),
    staleTime: 10 * 60_000,
  });
}
