import { useCallback, useState } from 'react';

export interface Position {
  lat: number;
  lng: number;
  /** Radius of the accuracy circle, in metres. */
  accuracy: number;
}

export type GeolocationStatus = 'idle' | 'locating' | 'granted' | 'denied' | 'unavailable';

export interface GeolocationState {
  position: Position | null;
  status: GeolocationStatus;
  message: string | null;
  locate: () => void;
}

const OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 10_000,
  maximumAge: 30_000,
};

/**
 * The officer's own position, used to centre the map when the field page opens.
 *
 * Denial is an ordinary outcome, not an error: the page then centres on the officer's
 * field-office region and says so, so the map is always usable.
 */
export function useGeolocation(): GeolocationState {
  const [position, setPosition] = useState<Position | null>(null);
  const [status, setStatus] = useState<GeolocationStatus>('idle');
  const [message, setMessage] = useState<string | null>(null);

  const locate = useCallback(() => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setStatus('unavailable');
      setMessage('This device cannot report its location.');
      return;
    }
    setStatus('locating');
    setMessage(null);
    navigator.geolocation.getCurrentPosition(
      (found) => {
        setPosition({
          lat: found.coords.latitude,
          lng: found.coords.longitude,
          accuracy: found.coords.accuracy,
        });
        setStatus('granted');
      },
      (error) => {
        setStatus(error.code === error.PERMISSION_DENIED ? 'denied' : 'unavailable');
        setMessage(
          error.code === error.PERMISSION_DENIED
            ? 'Location permission was declined, so the map is centred on your field office region.'
            : 'Your location could not be found, so the map is centred on your field office region.',
        );
      },
      OPTIONS,
    );
  }, []);

  return { position, status, message, locate };
}
