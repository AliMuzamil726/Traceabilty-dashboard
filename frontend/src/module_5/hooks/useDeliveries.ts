import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { deliveriesApi, deliveryKeys, type DeliveryParams } from '../api/client';

export const PAGE_SIZE = 25;

export function useDeliveryList(params: DeliveryParams) {
  return useQuery({
    queryKey: deliveryKeys.list(params),
    queryFn: ({ signal }) => deliveriesApi.list({ ...params, page_size: PAGE_SIZE }, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
}

export function useDelivery(id: string | null) {
  return useQuery({
    queryKey: deliveryKeys.detail(id ?? ''),
    queryFn: ({ signal }) => deliveriesApi.get(id as string, signal),
    enabled: Boolean(id),
  });
}

export function useDeliveryStats(params: DeliveryParams) {
  return useQuery({
    queryKey: deliveryKeys.stats(params),
    queryFn: ({ signal }) => deliveriesApi.stats(params, signal),
    refetchInterval: 60_000,
  });
}
