import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { isUkPostcode } from '@/core/utils/validators';
import { registerApi, registerKeys } from '../api/client';

const DEBOUNCE_MS = 400;

/**
 * Resolves a UK postcode to its county and region.
 *
 * The officer keeps typing, so the request is debounced by 400 ms and only fires once
 * the postcode is a valid shape. When the answer comes back unresolved, the form opens
 * the county and region fields for manual entry; that is the only time they are editable.
 */
export function usePostcode(postcode: string) {
  const [debounced, setDebounced] = useState('');

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(postcode.trim()), DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [postcode]);

  const valid = isUkPostcode(debounced);

  return useQuery({
    queryKey: registerKeys.postcode(debounced.toUpperCase().replace(/\s+/g, '')),
    queryFn: ({ signal }) => registerApi.postcode(debounced, signal),
    enabled: valid,
    staleTime: 24 * 60 * 60_000,
    retry: false,
  });
}
