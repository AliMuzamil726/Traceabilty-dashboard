import { useMemo } from 'react';
import { useMapConfig } from '@/module_8';
import { LABELS, REGION_CENTRES, SATELLITE, STREET, type TileLayerConfig } from './tileLayers';

export interface BaseLayers {
  /** The layer an administrator chose in Settings (MapTiler Hybrid HD imagery by default). */
  satellite: TileLayerConfig;
  street: TileLayerConfig;
  labels: TileLayerConfig;
  /** Whether the place-name overlay starts switched on. */
  labelsOn: boolean;
  centres: Record<string, { lat: number; lng: number; zoom: number }>;
}

/**
 * The tile layers every map in the product draws, taken from Settings with MapTiler
 * Hybrid 2026 HD (maxZoom 22, tileSize 512, zoomOffset -1) as the default base layer.
 */
export function useTileLayers(): BaseLayers {
  const config = useMapConfig();

  return useMemo(() => {
    const chosen = config.tiles;
    const isLegacyEsri =
      chosen.key === 'esri_imagery' || chosen.url.includes('arcgisonline.com');
    const isMaptiler = chosen.url.includes('api.maptiler.com');

    // Use MapTiler Hybrid 2026 HD whenever the server is on the default imagery setting
    // or unreachable, while still respecting explicit custom XYZ tile overrides.
    const primary: TileLayerConfig = isLegacyEsri
      ? SATELLITE
      : {
          id: chosen.key,
          label: chosen.label,
          url: chosen.url,
          attribution: chosen.attribution || SATELLITE.attribution,
          maxZoom: Math.max(chosen.max_zoom ?? 22, 22),
          tileSize: chosen.tile_size ?? (isMaptiler ? 512 : SATELLITE.tileSize),
          zoomOffset: chosen.zoom_offset ?? (isMaptiler ? -1 : SATELLITE.zoomOffset),
        };

    const resolvedCentres = config.centres
      ? {
          ...REGION_CENTRES,
          ...config.centres,
          PK: {
            lat: config.centres.PK?.lat ?? REGION_CENTRES.PK!.lat,
            lng: config.centres.PK?.lng ?? REGION_CENTRES.PK!.lng,
            zoom: 18,
          },
        }
      : REGION_CENTRES;

    return {
      satellite: chosen.key === 'esri_street' ? SATELLITE : primary,
      street: chosen.key === 'esri_street' ? primary : STREET,
      labels: config.labelsOverlayUrl
        ? { ...LABELS, url: config.labelsOverlayUrl, attribution: primary.attribution, maxZoom: 22 }
        : LABELS,
      labelsOn: config.labelsOverlay,
      centres: resolvedCentres,
    };
  }, [config.tiles, config.labelsOverlay, config.labelsOverlayUrl, config.centres]);
}
