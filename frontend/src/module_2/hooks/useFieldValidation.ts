import { useCallback, useEffect, useRef, useState } from 'react';
import { registerApi } from '../api/client';
import type { GeometryValidation, PolygonGeometry } from '../api/types';

const DEBOUNCE_MS = 350;

export interface FieldValidationState {
  result: GeometryValidation | null;
  checking: boolean;
  /** True only when the server has confirmed the boundary is saveable. */
  canSave: boolean;
}

/**
 * Live geometry and overlap checking while the officer draws.
 *
 * The server is authoritative, so the Save button follows its answer and nothing else.
 * Three details matter: the check is debounced because vertices move continuously; each
 * new check aborts the one before it so a slow answer cannot overwrite a newer one; and
 * `canSave` starts false and only becomes true on a positive answer, so a boundary is
 * never saveable merely because no answer has arrived yet.
 */
export function useFieldValidation(
  farmerId: string,
  excludeFieldId?: string | null,
): FieldValidationState & {
  check: (geometry: PolygonGeometry | null, pin?: { lat: number; lng: number } | null) => void;
  reset: () => void;
} {
  const [result, setResult] = useState<GeometryValidation | null>(null);
  const [checking, setChecking] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const cancel = useCallback(() => {
    window.clearTimeout(timer.current);
    controller.current?.abort();
    controller.current = null;
  }, []);

  const reset = useCallback(() => {
    cancel();
    setResult(null);
    setChecking(false);
  }, [cancel]);

  const check = useCallback(
    (geometry: PolygonGeometry | null, pin?: { lat: number; lng: number } | null) => {
      cancel();
      if (!geometry) {
        setResult(null);
        setChecking(false);
        return;
      }
      setChecking(true);
      timer.current = window.setTimeout(() => {
        const next = new AbortController();
        controller.current = next;
        registerApi
          .validateGeometry(
            {
              farmer_id: farmerId,
              geometry,
              pin_lat: pin?.lat ?? null,
              pin_lng: pin?.lng ?? null,
              exclude_field_id: excludeFieldId ?? null,
            },
            next.signal,
          )
          .then((answer) => {
            if (!next.signal.aborted) setResult(answer);
          })
          .catch(() => {
            // An aborted check is normal; a failed one leaves Save disabled, which is
            // the safe default because the overlap rule is enforced server-side.
            if (!next.signal.aborted) setResult(null);
          })
          .finally(() => {
            if (!next.signal.aborted) setChecking(false);
          });
      }, DEBOUNCE_MS);
    },
    [cancel, farmerId, excludeFieldId],
  );

  useEffect(() => cancel, [cancel]);

  return { result, checking, canSave: result?.valid === true && !checking, check, reset };
}
