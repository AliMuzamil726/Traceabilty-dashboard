/**
 * Unit conversions. Storage is always SI (square metres, kilograms); display units
 * depend on the crop programme: cotton (Pakistan) uses acres and maunds, hemp (UK)
 * uses hectares and tonnes.
 */

export const M2_PER_ACRE = 4046.8564224;
export const M2_PER_HECTARE = 10_000;
export const KG_PER_MAUND = 40;
export const KG_PER_TONNE = 1000;

export type AreaUnit = 'acre' | 'ha' | 'm2';
export type MassUnit = 'kg' | 'maund' | 't';

export const AREA_LABEL: Record<AreaUnit, string> = { acre: 'acres', ha: 'ha', m2: 'm²' };
export const MASS_LABEL: Record<MassUnit, string> = { kg: 'kg', maund: 'maunds', t: 't' };

export function m2ToAcres(m2: number): number {
  return m2 / M2_PER_ACRE;
}
export function acresToM2(acres: number): number {
  return acres * M2_PER_ACRE;
}
export function m2ToHectares(m2: number): number {
  return m2 / M2_PER_HECTARE;
}
export function hectaresToM2(ha: number): number {
  return ha * M2_PER_HECTARE;
}

export function convertArea(m2: number, unit: AreaUnit): number {
  if (unit === 'acre') return m2ToAcres(m2);
  if (unit === 'ha') return m2ToHectares(m2);
  return m2;
}

export function kgToMaunds(kg: number): number {
  return kg / KG_PER_MAUND;
}
export function maundsToKg(maunds: number): number {
  return maunds * KG_PER_MAUND;
}

export function convertMass(kg: number, unit: MassUnit): number {
  if (unit === 'maund') return kgToMaunds(kg);
  if (unit === 't') return kg / KG_PER_TONNE;
  return kg;
}

export interface UnitSystem {
  area: AreaUnit;
  mass: MassUnit;
}

/** Display units for a crop programme. */
export function unitsForCrop(crop: 'cotton' | 'hemp' | string): UnitSystem {
  return crop === 'hemp' ? { area: 'ha', mass: 't' } : { area: 'acre', mass: 'maund' };
}
