import { useMutation, useQueryClient } from '@tanstack/react-query';
import { radarApi, radarKeys } from '../api/client';
import type { Crop } from '../api/types';

export interface RequestPickupInput {
  crop: Crop;
  season_year: number;
  field_ids: string[];
  preferred_date?: string | null;
  note?: string | null;
}

/** Bulk request; every radar view refreshes afterwards. */
export function useRequestPickup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: RequestPickupInput) => radarApi.requestPickup(input),
    onSuccess: () => client.invalidateQueries({ queryKey: radarKeys.all }),
  });
}

export function useCancelPickup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => radarApi.cancel(id, reason),
    onSuccess: () => client.invalidateQueries({ queryKey: radarKeys.all }),
  });
}
