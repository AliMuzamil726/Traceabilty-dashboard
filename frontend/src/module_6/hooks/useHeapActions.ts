import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@/core/api/errors';
import { toast } from '@/design-system/components';
import { heapKeys, heapsApi } from '../api/client';
import type { HeapDetail } from '../api/types';

/** Every heap change refreshes heaps and deliveries (a delivery's heap is shown there too). */
function useRefresh() {
  const client = useQueryClient();
  return (detail?: HeapDetail) => {
    if (detail) client.setQueryData(heapKeys.detail(detail.id), detail);
    void client.invalidateQueries({ queryKey: heapKeys.all });
    void client.invalidateQueries({ queryKey: ['deliveries'] });
  };
}

function fail(title: string) {
  return (e: unknown) => toast.error(title, toApiError(e).message);
}

export function useHeapActions(key: string) {
  const refresh = useRefresh();
  return {
    update: useMutation({
      mutationFn: (body: Parameters<typeof heapsApi.update>[1]) => heapsApi.update(key, body),
      onSuccess: refresh,
      onError: fail('Not saved'),
    }),
    addDeliveries: useMutation({
      mutationFn: (ids: string[]) => heapsApi.addDeliveries(key, ids),
      onSuccess: (r) => refresh(r.heap),
      onError: fail('Not added'),
    }),
    removeDelivery: useMutation({
      mutationFn: ({ id, reason }: { id: string; reason: string }) => heapsApi.removeDelivery(key, id, reason),
      onSuccess: refresh,
    }),
    createBales: useMutation({
      mutationFn: (count: number) => heapsApi.createBales(key, count),
      onSuccess: refresh,
    }),
    voidBale: useMutation({
      mutationFn: ({ serial, reason }: { serial: string; reason: string }) => heapsApi.voidBale(serial, reason),
      onSuccess: () => refresh(),
    }),
    close: useMutation({
      mutationFn: (body: { reason?: string | null; with_remainder?: boolean }) => heapsApi.close(key, body),
      onSuccess: refresh,
    }),
  };
}

export function useOpenHeap() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ siteId, note }: { siteId: string; note?: string }) => heapsApi.open(siteId, note),
    onSuccess: (r) => refresh(r.heap),
  });
}

/** Put one delivered delivery into a heap. Exported for Deliveries (Module 5). */
export function useAssignToHeap() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ heapId, deliveryId }: { heapId: string; deliveryId: string }) => {
      const r = await heapsApi.addDeliveries(heapId, [deliveryId]);
      const skipped = r.skipped[0];
      if (skipped) throw new Error(skipped.reason);
      return r.heap;
    },
    onSuccess: refresh,
  });
}
