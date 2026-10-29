import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { gateApi, gateKeys, type GateEntryParams, type GateSiteParams } from '../api/client';

export function useGateSummary(params: GateSiteParams, enabled = true) {
  return useQuery({
    queryKey: gateKeys.summary(params),
    queryFn: ({ signal }) => gateApi.summary(params, signal),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useInbound(params: GateSiteParams, enabled = true) {
  return useQuery({
    queryKey: gateKeys.inbound(params),
    queryFn: ({ signal }) => gateApi.inbound(params, signal),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useGateEntries(params: GateEntryParams, enabled = true) {
  return useQuery({
    queryKey: gateKeys.entries(params),
    queryFn: ({ signal }) => gateApi.entries(params, signal),
    enabled,
    placeholderData: keepPreviousData,
  });
}

/** Arriving, accepting and rejecting all change the gate figures and the delivery. */
export function useGateActions() {
  const client = useQueryClient();
  const refresh = () => {
    void client.invalidateQueries({ queryKey: gateKeys.all });
    void client.invalidateQueries({ queryKey: ['deliveries'] });
    void client.invalidateQueries({ queryKey: ['radar'] });
  };
  return {
    arrive: useMutation({ mutationFn: gateApi.arrive, onSuccess: refresh }),
    accept: useMutation({
      mutationFn: ({ entryId, body }: { entryId: string; body: Parameters<typeof gateApi.accept>[1] }) =>
        gateApi.accept(entryId, body),
      onSuccess: refresh,
    }),
    reject: useMutation({
      mutationFn: ({ entryId, reason }: { entryId: string; reason: string }) =>
        gateApi.reject(entryId, reason),
      onSuccess: refresh,
    }),
  };
}
