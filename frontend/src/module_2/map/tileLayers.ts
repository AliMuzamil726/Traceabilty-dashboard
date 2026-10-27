/**
 * Map tile sources, all in one file so they can be swapped without touching the map.
 *
 * Upgraded to MapTiler Hybrid 2026 HD tiles (512px retina-grade tiles with zoomOffset -1
 * and maxZoom 22) for farm-level cotton fibre traceability without "No Data Available"
 * errors at high zoom levels.
 */

export interface TileLayerConfig {
  id: string;
  label: string;
  url: string;
  attribution: string;
  maxZoom: number;
  tileSize?: number;
  zoomOffset?: number;
  /** Drawn over the base layer rather than instead of it. */
  overlay?: boolean;
}

export const MAPTILER_KEY = 'ynaKX4hm3oPNgWdaY1Hg';

export const MAPTILER_ATTRIBUTION = '© MapTiler © OpenStreetMap';
const ESRI_STREET_ATTRIBUTION = 'Map data &copy; Esri, HERE, Garmin, OpenStreetMap contributors';

export const SATELLITE: TileLayerConfig = {
  id: 'satellite',
  label: 'Satellite',
  url: `https://api.maptiler.com/maps/hybrid/{z}/{x}/{y}.jpg?key=${MAPTILER_KEY}`,
  attribution: MAPTILER_ATTRIBUTION,
  maxZoom: 22,
  tileSize: 512,
  zoomOffset: -1,
};

export const STREET: TileLayerConfig = {
  id: 'street',
  label: 'Street',
  url: `https://api.maptiler.com/maps/streets-v2/{z}/{x}/{y}.png?key=${MAPTILER_KEY}`,
  attribution: MAPTILER_ATTRIBUTION,
  maxZoom: 22,
  tileSize: 512,
  zoomOffset: -1,
};

/** Place and road names, drawn on top of the imagery when the officer wants them. */
export const LABELS: TileLayerConfig = {
  id: 'labels',
  label: 'Labels',
  url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
  attribution: ESRI_STREET_ATTRIBUTION,
  maxZoom: 22,
  overlay: true,
};

export const BASE_LAYERS: readonly TileLayerConfig[] = [SATELLITE, STREET];

export type BaseLayerId = 'satellite' | 'street';

/** Fallback centres per field-office region, used when geolocation is unavailable. */
export const REGION_CENTRES: Record<string, { lat: number; lng: number; zoom: number }> = {
  PK: { lat: 30.1575, lng: 71.5249, zoom: 18 }, // Multan, the cotton belt (farm-level default zoom 18)
  GB: { lat: 53.2307, lng: -0.5406, zoom: 18 }, // Lincolnshire, the hemp programme
};

export const DEFAULT_ZOOM = 18;

/** Below this zoom the field layer is clustered points; at or above it, outlines. */
export const GEOMETRY_ZOOM = 13;
