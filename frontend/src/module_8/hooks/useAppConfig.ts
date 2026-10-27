import { useQuery } from '@tanstack/react-query';
import { settingsApi, settingsKeys } from '../api/client';
import type { PublicConfig, TileLayer } from '../api/types';

/**
 * The configuration every screen needs before it can draw: map tiles and their
 * attribution, the QR base URL, the season label.
 *
 * Every map in the product reads its tile layer from here, so changing the provider in
 * Settings changes all of them at once and the credit line a tile licence requires can
 * never drift between screens. The endpoint is public (it holds no secret), so this
 * works on the public trace page too, where nobody is signed in.
 */
export function useAppConfig() {
  return useQuery({
    queryKey: settingsKeys.public,
    queryFn: ({ signal }) => settingsApi.publicConfig(signal),
    staleTime: 60_000,
    retry: 1,
  });
}

/** The tile layer used when the server cannot be reached, so a map still renders. */
export const FALLBACK_TILES: TileLayer = {
  key: 'maptiler_hybrid',
  label: 'MapTiler Hybrid HD',
  url: 'https://api.maptiler.com/maps/hybrid/{z}/{x}/{y}.jpg?key=ynaKX4hm3oPNgWdaY1Hg',
  attribution: '© MapTiler © OpenStreetMap',
  max_zoom: 22,
  tile_size: 512,
  zoom_offset: -1,
};

/** Map settings with the fallback applied, for a component that cannot wait. */
export function useMapConfig(): {
  tiles: TileLayer;
  labelsOverlay: boolean;
  labelsOverlayUrl: string | null;
  centres: PublicConfig['map']['centres'] | null;
  geolocationPrompt: boolean;
  loading: boolean;
} {
  const { data, isLoading } = useAppConfig();
  return {
    // Every read is optional: a map must still draw when the server is unreachable or
    // answers with something unexpected, so a missing field never throws here.
    tiles: data?.map?.tiles ?? FALLBACK_TILES,
    labelsOverlay: data?.map?.labels_overlay ?? false,
    labelsOverlayUrl: data?.map?.labels_overlay_url ?? null,
    centres: data?.map?.centres ?? null,
    geolocationPrompt: data?.map?.geolocation_prompt ?? true,
    loading: isLoading,
  };
}
