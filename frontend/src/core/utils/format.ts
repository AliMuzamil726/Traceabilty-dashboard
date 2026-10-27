/** Display formatting. All output is English (en-GB conventions: 19 Oct 2026, 1,234.5). */

const LOCALE = 'en-GB';
const EMPTY = '-';

export function formatNumber(value: number | null | undefined, maximumFractionDigits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits }).format(value);
}

export function formatDecimal(value: number | null | undefined, fractionDigits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

export function formatPercent(ratio: number | null | undefined, fractionDigits = 0): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return EMPTY;
  return new Intl.NumberFormat(LOCALE, {
    style: 'percent',
    maximumFractionDigits: fractionDigits,
  }).format(ratio);
}

/** Compact counts for KPI cards: 1,240 / 12.5k / 3.1M. */
export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  if (Math.abs(value) < 10_000) return formatNumber(value);
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })
    .format(value)
    .toLowerCase()
    .replace('m', 'M')
    .replace('b', 'B');
}

export function formatWithUnit(
  value: number | null | undefined,
  unit: string,
  fractionDigits = 2,
): string {
  const n = formatNumber(value, fractionDigits);
  return n === EMPTY ? EMPTY : `${n} ${unit}`;
}

function toDate(value: string | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === '') return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** 19 Oct 2026 */
export function formatDate(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return EMPTY;
  return new Intl.DateTimeFormat(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' }).format(date);
}

/** 19 Oct 2026, 14:05 (local time) */
export function formatDateTime(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return EMPTY;
  return new Intl.DateTimeFormat(LOCALE, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

/** Coordinates with fixed precision for monospace display. */
export function formatCoordinate(value: number | null | undefined, digits = 6): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  return value.toFixed(digits);
}

/** "Muhammad Imran Khan" -> "MK" */
export function initials(name: string | null | undefined): string {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${formatNumber(count)} ${count === 1 ? singular : plural}`;
}

const COUNTRY_NAMES: Record<string, string> = { PK: 'Pakistan', GB: 'United Kingdom' };

export function countryName(code: string | null | undefined): string {
  if (!code) return EMPTY;
  return COUNTRY_NAMES[code.toUpperCase()] ?? code.toUpperCase();
}

export function roleLabel(role: string | null | undefined): string {
  if (role === 'admin') return 'Administrator';
  if (role === 'officer') return 'Field officer';
  if (role === 'staff') return 'Staff';
  return role ?? EMPTY;
}
