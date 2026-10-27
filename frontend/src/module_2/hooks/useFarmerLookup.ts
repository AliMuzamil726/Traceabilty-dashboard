import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { isCnic, normalizeIdNumber } from '@/core/utils/validators';
import { registerApi, registerKeys } from '../api/client';
import { HEMP_ID_MAX_DIGITS, HEMP_ID_MIN_DIGITS } from '../api/schemas';
import type { Crop } from '../api/types';

const DEBOUNCE_MS = 400;

/** Is this ID number complete enough to be worth asking the server about? */
export function isLookupReady(idNumber: string, crop: Crop): boolean {
  if (crop === 'cotton') return isCnic(idNumber);
  const digits = normalizeIdNumber(idNumber);
  return (
    /^\d+$/.test(digits) &&
    digits.length >= HEMP_ID_MIN_DIGITS &&
    digits.length <= HEMP_ID_MAX_DIGITS
  );
}

/**
 * Looks the ID number up as soon as it becomes valid, which is what makes the SAWIE ID
 * chip appear under the field. Debounced, because the officer is still typing, and
 * disabled entirely until the number is complete so half-typed numbers are never sent.
 */
export function useFarmerLookup(idNumber: string, crop: Crop) {
  const [debounced, setDebounced] = useState('');

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(idNumber), DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [idNumber]);

  const ready = isLookupReady(debounced, crop);

  return useQuery({
    queryKey: registerKeys.lookup(normalizeIdNumber(debounced), crop),
    queryFn: ({ signal }) => registerApi.lookupFarmer(debounced, crop, signal),
    enabled: ready,
    staleTime: 30_000,
    retry: false,
  });
}
