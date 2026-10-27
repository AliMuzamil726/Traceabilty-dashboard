/**
 * Variance preview for the Receive dialog. Mirrors backend/module_5/services/weights.py
 * so the officer sees the level before confirming; the server recomputes and decides.
 */
import type { Thresholds, VarianceLevel } from '../api/types';

export const KG_PER_MAUND = 40;

export interface VariancePreview {
  reference: 'field_weight' | 'estimate' | null;
  referenceKg: number | null;
  varianceKg: number | null;
  variancePct: number | null;
  level: VarianceLevel | null;
}

const round = (value: number, places: number) => {
  const f = 10 ** places;
  return Math.round((value + Number.EPSILON * Math.sign(value)) * f) / f;
};

export function previewVariance(
  weighbridgeKg: number | null,
  fieldWeightKg: number | null,
  estimatedKg: number | null,
  t: Pick<Thresholds, 'variance_warn_pct' | 'variance_flag_pct'>,
): VariancePreview {
  const reference = fieldWeightKg ? 'field_weight' : estimatedKg ? 'estimate' : null;
  const referenceKg = fieldWeightKg || estimatedKg || null;
  if (!weighbridgeKg || weighbridgeKg <= 0 || !referenceKg || !reference) {
    return { reference, referenceKg, varianceKg: null, variancePct: null, level: null };
  }
  const diff = weighbridgeKg - referenceKg;
  const pct = round((diff / referenceKg) * 100, 2);
  const size = Math.abs(pct);
  const level: VarianceLevel = size >= t.variance_flag_pct ? 'flag' : size >= t.variance_warn_pct ? 'warn' : 'ok';
  return { reference, referenceKg, varianceKg: round(diff, 1), variancePct: pct, level };
}

export function maunds(kg: number | null | undefined): number | null {
  return kg === null || kg === undefined ? null : round(kg / KG_PER_MAUND, 1);
}

export function kgText(kg: number | null | undefined, crop: 'cotton' | 'hemp'): string {
  if (kg === null || kg === undefined) return '-';
  const base = `${kg.toLocaleString('en-GB', { maximumFractionDigits: 1 })} kg`;
  return crop === 'cotton' ? `${base} (${(maunds(kg) ?? 0).toLocaleString('en-GB', { maximumFractionDigits: 1 })} maunds)` : base;
}

export function siteWord(crop: 'cotton' | 'hemp'): { site: string; lot: string } {
  return crop === 'cotton' ? { site: 'Ginner', lot: 'Heap' } : { site: 'Processor', lot: 'Batch' };
}
