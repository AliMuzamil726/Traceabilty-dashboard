import { useQuery } from '@tanstack/react-query';
import { api } from '@/core/api/client';
import type { Page } from '@/core/api/types';

export interface FieldOffice {
  id: string;
  code: string;
  name: string;
  country: string;
  province: string | null;
  district: string | null;
  is_dummy: boolean;
  active: boolean;
}

/**
 * Field offices for one country, from the shared endpoint.
 *
 * Scoped by country rather than fetched wholesale, because the crop decides the
 * country and an officer must not be able to file a Pakistani farmer to a UK office.
 */
export function useFieldOffices(country: string) {
  return useQuery({
    queryKey: ['offices', country],
    queryFn: async ({ signal }) => {
      const page = await api.get<Page<FieldOffice>>(
        '/v1/offices',
        { country, page_size: 200 },
        signal,
      );
      return page.items;
    },
    staleTime: 10 * 60_000,
  });
}
