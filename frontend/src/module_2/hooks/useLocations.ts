import { useQuery } from '@tanstack/react-query';
import { registerApi, registerKeys } from '../api/client';

/**
 * The province to district to tehsil cascade. Each level only loads once the level
 * above it has been chosen, so the queries are disabled rather than fired with a
 * placeholder, and the dependent Select stays disabled with an empty option list.
 */
export function useProvinces(country: string, enabled = true) {
  return useQuery({
    queryKey: registerKeys.provinces(country),
    queryFn: ({ signal }) => registerApi.provinces(country, signal),
    enabled,
    staleTime: 60 * 60_000,
  });
}

export function useDistricts(provinceCode: string | null, country: string) {
  return useQuery({
    queryKey: registerKeys.districts(provinceCode),
    queryFn: ({ signal }) => registerApi.districts(provinceCode as string, country, signal),
    enabled: Boolean(provinceCode),
    staleTime: 60 * 60_000,
  });
}

export function useTehsils(districtCode: string | null, country: string) {
  return useQuery({
    queryKey: registerKeys.tehsils(districtCode),
    queryFn: ({ signal }) => registerApi.tehsils(districtCode as string, country, signal),
    enabled: Boolean(districtCode),
    staleTime: 60 * 60_000,
  });
}

/** Villages other officers already entered in this tehsil, so spellings converge. */
export function useVillageSuggestions(tehsilName: string | null, query: string) {
  return useQuery({
    queryKey: registerKeys.villages(tehsilName, query),
    queryFn: ({ signal }) =>
      registerApi.villageSuggestions(tehsilName as string, query || undefined, signal),
    enabled: Boolean(tehsilName),
    staleTime: 5 * 60_000,
  });
}
