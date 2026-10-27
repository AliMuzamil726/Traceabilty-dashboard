import { useQueries, useQuery } from '@tanstack/react-query';
import { api } from '@/core/api/client';
import type { MasterList } from '@/core/api/types';
import { sharedKeys } from '@/core/hooks/useSharedData';
import { fieldbookApi, fieldbookKeys } from '../api/client';
import type { Crop, FormDefinition } from '../api/types';

/** The crop's form definition. It changes only with a release, so it is cached for long. */
export function useFormSchema(crop: Crop | undefined) {
  return useQuery({
    queryKey: fieldbookKeys.schema(crop ?? 'cotton'),
    queryFn: ({ signal }) => fieldbookApi.schema(crop as Crop, signal),
    enabled: Boolean(crop),
    staleTime: 60 * 60_000,
  });
}

/** Labels for every master list a definition uses, so summaries show words, not codes. */
export function useListLabels(definition: FormDefinition | undefined) {
  const keys = definition
    ? [...new Set(definition.steps.flatMap((s) => s.fields.map((f) => f.list_key).filter(Boolean) as string[]))]
    : [];
  const results = useQueries({
    queries: keys.map((key) => ({
      queryKey: sharedKeys.master(key, definition?.country, definition?.crop),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        api.get<MasterList>(`/v1/master/${key}`, { country: definition?.country, crop: definition?.crop }, signal),
      staleTime: 10 * 60_000,
    })),
  });
  const table = new Map<string, Map<string, string>>();
  results.forEach((r, i) => {
    const key = keys[i];
    if (key && r.data) table.set(key, new Map(r.data.items.map((o) => [o.value, o.label])));
  });
  return (listKey: string, value: string): string => table.get(listKey)?.get(value) ?? value;
}
