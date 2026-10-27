import { useQuery } from '@tanstack/react-query';
import { ApiError } from '@/core/api/errors';
import { qrApi, qrKeys } from '../api/client';

/** The public page's data. A 404 (unknown or revoked) is final, so it is not retried. */
export function usePublicTrace(token: string) {
  return useQuery({
    queryKey: qrKeys.publicTrace(token),
    queryFn: ({ signal }) => qrApi.publicTrace(token, signal),
    staleTime: 60_000,
    retry: (count, error) => !(error instanceof ApiError && (error.status === 404 || error.status === 429)) && count < 2,
  });
}
