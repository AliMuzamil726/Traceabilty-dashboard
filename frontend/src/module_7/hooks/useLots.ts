import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { qrApi, qrKeys } from '../api/client';
import type { Crop } from '../api/types';
import { fetchBlob } from '../lib/download';

export function useLots(params: { crop?: Crop; site_id?: string }, enabled = true) {
  return useQuery({
    queryKey: qrKeys.lots(params),
    queryFn: ({ signal }) => qrApi.lots(params, signal),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useLotOverview(heapId: string | null) {
  return useQuery({
    queryKey: qrKeys.overview(heapId ?? ''),
    queryFn: ({ signal }) => qrApi.overview(heapId ?? '', signal),
    enabled: Boolean(heapId),
  });
}

export function useBales(heapId: string | null) {
  return useQuery({
    queryKey: qrKeys.bales(heapId ?? ''),
    queryFn: ({ signal }) => qrApi.bales(heapId ?? '', signal),
    enabled: Boolean(heapId),
  });
}

/** Revoke and regenerate (administrators). Both refresh the lot. */
export function useQrActions() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: qrKeys.all });
  return {
    revoke: useMutation({ mutationFn: (v: { token: string; reason: string }) => qrApi.revoke(v.token, v.reason), onSuccess: refresh }),
    regenerate: useMutation({ mutationFn: (v: { serial: string; reason: string }) => qrApi.regenerate(v.serial, v.reason), onSuccess: refresh }),
    refresh,
  };
}

/** The QR image as an object URL, fetched with the officer header. */
export function useQrImage(token: string | null, size = 8): string | null {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    if (!token) { setSrc(null); return undefined; }
    let url: string | null = null;
    let live = true;
    fetchBlob(qrApi.pngPath(token, size))
      .then(({ blob }) => { if (live) { url = URL.createObjectURL(blob); setSrc(url); } })
      .catch(() => { if (live) setSrc(null); });
    return () => { live = false; if (url) URL.revokeObjectURL(url); };
  }, [token, size]);
  return src;
}
