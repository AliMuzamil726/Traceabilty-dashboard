import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { heapKeys, heapsApi } from '../api/client';
import type { Crop } from '../api/types';

export function useHeaps(params: { crop?: Crop; site_id?: string; status?: 'open' | 'closed' }, enabled = true) {
  return useQuery({
    queryKey: heapKeys.list(params),
    queryFn: ({ signal }) => heapsApi.list(params, signal),
    enabled,
    placeholderData: keepPreviousData,
  });
}
