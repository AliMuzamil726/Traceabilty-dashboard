import { useMutation, useQueryClient } from '@tanstack/react-query';
import { deliveriesApi, deliveryKeys } from '../api/client';
import type { DeliveryDetail, ScheduleInput } from '../api/types';

/** Deliveries, the Radar view and heaps all change together. */
function useRefresh() {
  const client = useQueryClient();
  return (detail?: DeliveryDetail) => {
    if (detail) client.setQueryData(deliveryKeys.detail(detail.id), detail);
    void client.invalidateQueries({ queryKey: deliveryKeys.all });
    void client.invalidateQueries({ queryKey: ['radar'] });
    void client.invalidateQueries({ queryKey: ['heaps'] });
  };
}

export function useSchedule() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (body: ScheduleInput) => deliveriesApi.schedule(body), onSuccess: () => refresh() });
}

export function useTransition(id: string) {
  const refresh = useRefresh();
  return {
    update: useMutation({
      mutationFn: (body: Partial<ScheduleInput>) => deliveriesApi.update(id, body),
      onSuccess: refresh,
    }),
    dispatch: useMutation({
      mutationFn: (body: { field_weight_kg?: number | null; note?: string | null }) => deliveriesApi.dispatch(id, body),
      onSuccess: (r) => refresh(r.delivery),
    }),
    receive: useMutation({
      mutationFn: (body: { weighbridge_weight_kg: number; moisture_pct: number; note?: string | null }) =>
        deliveriesApi.receive(id, body),
      onSuccess: (r) => refresh(r.delivery),
    }),
    cancel: useMutation({
      mutationFn: (reason: string) => deliveriesApi.cancel(id, reason),
      onSuccess: refresh,
    }),
    correct: useMutation({
      mutationFn: (body: { reason: string; weighbridge_weight_kg?: number | null; moisture_pct?: number | null }) =>
        deliveriesApi.correct(id, body),
      onSuccess: (r) => refresh(r.delivery),
    }),
  };
}
