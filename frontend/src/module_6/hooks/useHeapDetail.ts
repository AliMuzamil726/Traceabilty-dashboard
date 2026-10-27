import { useQuery } from '@tanstack/react-query';
import { heapKeys, heapsApi } from '../api/client';

export function useHeapDetail(key: string | null) {
  return useQuery({
    queryKey: heapKeys.detail(key ?? ''),
    queryFn: ({ signal }) => heapsApi.get(key as string, signal),
    enabled: Boolean(key),
  });
}
