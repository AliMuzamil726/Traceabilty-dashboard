import { useQuery } from '@tanstack/react-query';
import { deliveriesApi, deliveryKeys, type DeliveryParams } from '../api/client';

/** Radar pickup requests waiting to be scheduled. */
export function useInbox(params: DeliveryParams) {
  return useQuery({
    queryKey: deliveryKeys.inbox(params),
    queryFn: ({ signal }) => deliveriesApi.inbox(params, signal),
    refetchInterval: 60_000,
  });
}
