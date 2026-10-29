/**
 * Net weight, variance preview and dialog validation for the gate.
 *
 * Mirrors backend/module_5/services/weights.py and the tolerance in force, so the
 * officer sees the level before confirming; the server recomputes and decides. A
 * load's reference weight is its field weight, else the pickup estimate.
 */
import type { GateEntry, GateStatus } from '../api/types';

export const KG_PER_MAUND = 40;

export type VarianceLevel = 'ok' | 'warn' | 'flag';

const round = (value: number, places: number) => {
  const f = 10 ** places;
  return Math.round((value + Number.EPSILON * Math.sign(value)) * f) / f;
};

export function netWeight(grossKg: number | null, tareKg: number | null): number | null {
  if (grossKg === null || tareKg === null) return null;
  return round(grossKg - tareKg, 2);
}

export interface ReferenceWeight {
  kg: number;
  label: 'field weight' | 'estimate';
}

export function referenceWeight(load: {
  field_weight_kg: number | null;
  estimated_quantity_kg: number | null;
}): ReferenceWeight | null {
  if (load.field_weight_kg) return { kg: load.field_weight_kg, label: 'field weight' };
  if (load.estimated_quantity_kg) return { kg: load.estimated_quantity_kg, label: 'estimate' };
  return null;
}

export interface VariancePreview {
  referenceKg: number;
  referenceLabel: string;
  varianceKg: number;
  variancePct: number;
  level: VarianceLevel;
}

export function previewVariance(
  netKg: number | null,
  entry: Pick<
    GateEntry,
    | 'field_weight_kg'
    | 'estimated_quantity_kg'
    | 'variance_warn_pct'
    | 'variance_flag_pct'
  >,
): VariancePreview | null {
  const reference = referenceWeight(entry);
  if (!netKg || netKg <= 0 || !reference) return null;
  if (entry.variance_warn_pct === null || entry.variance_flag_pct === null) return null;
  const diff = netKg - reference.kg;
  const pct = round((diff / reference.kg) * 100, 2);
  const size = Math.abs(pct);
  const level: VarianceLevel =
    size >= entry.variance_flag_pct ? 'flag' : size >= entry.variance_warn_pct ? 'warn' : 'ok';
  return {
    referenceKg: reference.kg,
    referenceLabel: reference.label,
    varianceKg: round(diff, 1),
    variancePct: pct,
    level,
  };
}

/** Colouring stays in the two-colour palette; the error red only for a flag. */
export const LEVEL_CLASSES: Record<VarianceLevel, string> = {
  ok: 'text-forest-700',
  warn: 'text-wheat-600',
  flag: 'text-danger',
};

export const LEVEL_LABEL: Record<VarianceLevel, string> = {
  ok: 'Within limits',
  warn: 'Check',
  flag: 'Flagged',
};

export interface AcceptInput {
  gross: number | null;
  tare: number | null;
  moisture: number | null;
  note: string;
}

/** Field errors keyed by API field name, so a server 422 lands on the same field. */
export function validateAccept(
  input: AcceptInput,
  entry: Pick<
    GateEntry,
    'field_weight_kg' | 'estimated_quantity_kg' | 'variance_warn_pct' | 'variance_flag_pct'
  >,
): Record<string, string> {
  const found: Record<string, string> = {};
  if (input.gross === null || input.gross <= 0) {
    found.gross_weight_kg = 'Enter the gross weight, above 0 kg.';
  }
  if (input.tare === null || input.tare < 0) {
    found.tare_weight_kg = 'Enter the tare weight, 0 kg or more.';
  }
  if (!found.gross_weight_kg && !found.tare_weight_kg) {
    const net = netWeight(input.gross, input.tare);
    if (net !== null && net <= 0) {
      found.gross_weight_kg = 'The gross weight must be more than the tare weight.';
    }
  }
  if (input.moisture === null || input.moisture < 0 || input.moisture > 100) {
    found.moisture_pct = 'Enter moisture from 0 to 100 percent.';
  }
  const variance = previewVariance(netWeight(input.gross, input.tare), entry);
  if (variance?.level === 'flag' && !input.note.trim()) {
    found.note = `The weight differs by more than ${entry.variance_flag_pct}%. Explain why.`;
  }
  return found;
}

export function validateReject(reason: string): string | null {
  const trimmed = reason.trim();
  if (trimmed.length < 3) return 'Give a reason for rejecting the load.';
  if (trimmed.length > 500) return 'Keep the reason under 500 characters.';
  return null;
}

export function maunds(kg: number | null | undefined): number | null {
  return kg === null || kg === undefined ? null : round(kg / KG_PER_MAUND, 1);
}

export function kgText(kg: number | null | undefined, crop: 'cotton' | 'hemp' = 'cotton'): string {
  if (kg === null || kg === undefined) return '-';
  const base = `${kg.toLocaleString('en-GB', { maximumFractionDigits: 1 })} kg`;
  return crop === 'cotton'
    ? `${base} (${(maunds(kg) ?? 0).toLocaleString('en-GB', { maximumFractionDigits: 1 })} maunds)`
    : base;
}

export function referenceText(load: {
  field_weight_kg: number | null;
  estimated_quantity_kg: number | null;
}): string {
  const reference = referenceWeight(load);
  return reference ? `${kgText(reference.kg)} ${reference.label}` : '-';
}

export const STATUS_LABEL: Record<GateStatus, string> = {
  pending: 'At the gate',
  accepted: 'Accepted',
  rejected: 'Rejected',
};

export const STATUS_CLASSES: Record<GateStatus, string> = {
  pending: 'border-wheat-300 bg-wheat-50 text-ink',
  accepted: 'border-forest-700 bg-forest-700 text-white',
  rejected: 'border-line bg-canvas text-muted',
};
