/**
 * Pure helpers over a form definition. The backend applies the same definition with the
 * same meaning (module_3/services/formschema.py); these mirror only what the screen needs
 * to react instantly: visibility, computed values, starting values, summaries and totals.
 * The server stays the authority on validation.
 */

import type { Entry, EntryData, FieldDef, StepDef, StepState } from '../api/types';

export function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined || value === '') return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as object).length === 0;
  return false;
}

/** `visible_if` against the entry's own values. Mirrors formschema.is_visible. */
export function isVisible(field: FieldDef, values: EntryData): boolean {
  const cond = field.visible_if;
  if (!cond) return true;
  const current = values[cond.field];
  if (cond.in) return typeof current === 'string' && cond.in.includes(current);
  if (cond.not_in) {
    if (current === null || current === undefined || current === '') return true;
    return typeof current !== 'string' || !cond.not_in.includes(current);
  }
  return true;
}

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function toDate(value: unknown): Date | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const d = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** A computed field's value. Mirrors formschema.compute. */
export function computeValue(field: FieldDef, values: EntryData): number | null {
  const spec = field.computed;
  if (!spec) return null;
  if (spec.kind === 'count') {
    const items = values[spec.of];
    return Array.isArray(items) ? items.filter((v) => !isEmpty(v)).length : 0;
  }
  if (spec.kind === 'days_between') {
    const from = toDate(values[spec.from]);
    const to = toDate(values[spec.to]);
    return from && to ? Math.round((to.getTime() - from.getTime()) / 86_400_000) : null;
  }
  let result = 1;
  for (const key of spec.of) {
    const n = toNumber(values[key]);
    if (n === null) return null;
    result *= n;
  }
  return Math.round(result * 10_000) / 10_000;
}

/** Values with every computed field filled in. */
export function withComputed(step: StepDef, values: EntryData): EntryData {
  const out = { ...values };
  for (const field of step.fields) if (field.computed) out[field.key] = computeValue(field, out);
  return out;
}

/** The values a new or existing entry starts from: saved data, then server defaults. */
export function initialValues(step: StepDef, defaults: Record<string, unknown>, entry?: Entry): EntryData {
  const values: EntryData = { ...(entry?.data ?? {}) };
  for (const field of step.fields) {
    if (field.default_from && (isEmpty(values[field.key]) || field.readonly)) {
      const fallback = defaults[field.default_from];
      if (!isEmpty(fallback)) values[field.key] = fallback;
    }
  }
  return withComputed(step, values);
}

/**
 * What is sent to the server: hidden, computed and photo fields are dropped (the server
 * recomputes and ignores them), and blank strings become absent.
 */
export function payloadFor(step: StepDef, values: EntryData): EntryData {
  const out: EntryData = {};
  for (const field of step.fields) {
    if (field.type === 'photos' || field.computed) continue;
    if (!isVisible(field, values)) continue;
    const value = values[field.key];
    if (isEmpty(value)) continue;
    out[field.key] = Array.isArray(value) ? value.filter((v) => !isEmpty(v)) : value;
  }
  return out;
}

export type LabelOf = (listKey: string, value: string) => string;

function formatValue(value: unknown): string {
  if (typeof value === 'number') return String(Math.round(value * 100) / 100);
  return String(value);
}

/** Fill the step's summary template. Mirrors formschema.summarise. */
export function summarise(step: StepDef, data: EntryData, labelOf: LabelOf): string {
  const template = step.summary ?? step.title;
  const lists = new Map(step.fields.map((f) => [f.key, f.list_key]));
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = data[key];
    if (isEmpty(value)) return '-';
    const listKey = lists.get(key);
    if (listKey && typeof value === 'string') return labelOf(listKey, value);
    return formatValue(value);
  });
}

export interface TotalLine {
  label: string;
  value: string;
}

/** The totals line shown above a repeatable step's entries. */
export function stepTotals(step: StepDef, entries: EntryData[]): TotalLine[] {
  return (step.totals ?? []).map((total) => {
    let sum = 0;
    if (total.kind === 'count') sum = entries.length;
    for (const data of total.kind === 'count' ? [] : entries) {
      if (total.kind === 'sum' && total.field) sum += toNumber(data[total.field]) ?? 0;
      if (total.kind === 'sum_product' && total.fields) {
        const parts = total.fields.map((k) => toNumber(data[k]));
        if (parts.every((p) => p !== null)) sum += (parts as number[]).reduce((a, b) => a * b, 1);
      }
      if (total.kind === 'sum_part' && total.field && total.part) {
        const parts = data[total.field] as Record<string, unknown> | undefined;
        sum += toNumber(parts?.[total.part]) ?? 0;
      }
    }
    if (total.factor) sum *= total.factor;
    const rounded = Math.round(sum * 100) / 100;
    return { label: total.label, value: total.unit ? `${rounded} ${total.unit}` : String(rounded) };
  });
}

/** A suggestion for a field from the step's suggestion map (fertiliser analysis). */
export function suggestionFor(step: StepDef, field: FieldDef, values: EntryData): unknown {
  const source = field.suggest_from;
  if (!source) return undefined;
  const chosen = values[source.field];
  if (typeof chosen !== 'string') return undefined;
  const row = step.suggestions?.[source.field]?.[chosen];
  if (!row) return undefined;
  if (source.part) return row[source.part];
  if (field.parts) return Object.fromEntries(field.parts.map((p) => [p.key, row[p.key] ?? 0]));
  return undefined;
}

/** Fields the officer must still answer before saving, so Save can point at them. */
export function missingRequired(step: StepDef, values: EntryData): string[] {
  return step.fields
    .filter((f) => f.required && !f.readonly && !f.computed && f.type !== 'photos' && isVisible(f, values))
    .filter((f) => isEmpty(values[f.key]))
    .map((f) => f.key);
}

export function stepDone(state: StepState | undefined): boolean {
  return state?.status === 'complete' || state?.status === 'not_applicable';
}
