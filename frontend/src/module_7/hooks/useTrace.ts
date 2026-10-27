import { useMutation, useQuery } from '@tanstack/react-query';
import { qrApi, qrKeys } from '../api/client';

export type TraceTarget = { kind: 'bale'; serial: string } | { kind: 'heap'; heapId: string };

/** The full internal chain for a bale or a lot. */
export function useTrace(target: TraceTarget | null) {
  const id = target ? (target.kind === 'bale' ? target.serial : target.heapId) : '';
  return useQuery({
    queryKey: qrKeys.trace(target?.kind ?? 'none', id),
    queryFn: ({ signal }) => (target?.kind === 'bale' ? qrApi.traceBale(id, signal) : qrApi.traceHeap(id, signal)),
    enabled: Boolean(target),
  });
}

export function useResolve() {
  return useMutation({ mutationFn: (q: string) => qrApi.resolve(q) });
}
