import type { PathOptions } from 'leaflet';

/**
 * Leaflet path styles, expressed in brand colours.
 *
 * Polygons use SAWiE brand colour #00A651, weight 3, fillOpacity 0.2 for crisp visibility
 * over high-resolution MapTiler Hybrid satellite imagery.
 */

export const SAWIE_BRAND_GREEN = '#00A651';
const FOREST_700 = '#1D6039';
const FOREST_500 = '#2F915A';
const WHEAT_500 = '#C79A2E';
const WHEAT_600 = '#A67C1F';
const DANGER = '#B42318';
const SURFACE = '#FFFFFF';

/** The boundary being drawn or edited now. */
export const DRAFT_STYLE: PathOptions = {
  color: SAWIE_BRAND_GREEN,
  weight: 3,
  opacity: 1,
  fillColor: SAWIE_BRAND_GREEN,
  fillOpacity: 0.2,
};

/** Another field of the same farmer: styled with SAWiE brand green #00A651, weight 3, fillOpacity 0.2. */
export const OWN_FIELD_STYLE: PathOptions = {
  color: SAWIE_BRAND_GREEN,
  weight: 3,
  opacity: 1,
  fillColor: SAWIE_BRAND_GREEN,
  fillOpacity: 0.2,
};

/** Every other cotton field in the database: styled with SAWiE brand green #00A651, weight 3, fillOpacity 0.2. */
export const OTHER_COTTON_STYLE: PathOptions = {
  color: SAWIE_BRAND_GREEN,
  weight: 3,
  opacity: 0.9,
  fillColor: SAWIE_BRAND_GREEN,
  fillOpacity: 0.2,
};

/** Every other hemp field: the same treatment in the accent colour. */
export const OTHER_HEMP_STYLE: PathOptions = {
  color: WHEAT_600,
  weight: 3,
  opacity: 0.85,
  fillColor: WHEAT_500,
  fillOpacity: 0.2,
};

/** The field selected in the left rail. */
export const SELECTED_STYLE: PathOptions = {
  color: SAWIE_BRAND_GREEN,
  weight: 3,
  opacity: 1,
  fillColor: SAWIE_BRAND_GREEN,
  fillOpacity: 0.2,
};

/**
 * The overlapping area. One of the three uses of the error red allowed by
 * DESIGN_SYSTEM.md, and the only colour on the map that means "fix this".
 */
export const OVERLAP_STYLE: PathOptions = {
  color: DANGER,
  weight: 2,
  opacity: 1,
  fillColor: DANGER,
  fillOpacity: 0.45,
  dashArray: '4 3',
};

/** The accuracy circle around the officer's reported position. */
export const ACCURACY_STYLE: PathOptions = {
  color: WHEAT_500,
  weight: 1,
  opacity: 0.8,
  fillColor: WHEAT_500,
  fillOpacity: 0.12,
};

export const PIN_STYLE: PathOptions = {
  color: SURFACE,
  weight: 2,
  fillColor: WHEAT_500,
  fillOpacity: 1,
};

export function styleForCrop(crop: string): PathOptions {
  return crop === 'hemp' ? OTHER_HEMP_STYLE : OTHER_COTTON_STYLE;
}

export { FOREST_500, FOREST_700 };
