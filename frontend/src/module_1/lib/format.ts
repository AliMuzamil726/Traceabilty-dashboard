/**
 * Dashboard wording and units.
 *
 * Units are never decided here from the crop: the server sends the unit it measured
 * in, and this file only writes it out. That is what keeps acres with cotton and
 * hectares with hemp on every screen.
 */
import { formatCompact, formatNumber } from '@/core/utils/format';
import { KG_PER_MAUND, KG_PER_TONNE } from '@/core/utils/units';
import type { Bucket, Crop, CropFilter } from '../api/types';

export const CROP_LABEL: Record<CropFilter, string> = {
  all: 'All crops',
  cotton: 'Cotton',
  hemp: 'Hemp',
};

/** A heap (cotton, at a ginner) or a batch (hemp, at a processor). */
export const LOT_LABEL: Record<Crop, string> = { cotton: 'Heap', hemp: 'Batch' };

export const BUCKET_ORDER: Bucket[] = [
  'no_sowing_data',
  'growing',
  'approaching',
  'ready',
  'harvested',
];

/** Hex values for Recharts and Leaflet, which take colour strings. Brand tokens only. */
export const HEX = {
  line: '#E3E6DE',
  muted: '#5B675F',
  ink: '#15221B',
  canvas: '#F5F6F2',
  surface: '#FFFFFF',
  wheat100: '#F7EBCB',
  wheat300: '#E3C479',
  wheat500: '#C79A2E',
  wheat600: '#A67C1F',
  forest50: '#F1F8F3',
  forest100: '#E3F1E8',
  forest500: '#2F915A',
  forest600: '#25774A',
  forest700: '#1D6039',
  forest900: '#10331F',
} as const;

export const BUCKET_HEX: Record<Bucket, string> = {
  no_sowing_data: HEX.line,
  growing: HEX.muted,
  approaching: HEX.wheat300,
  ready: HEX.forest600,
  harvested: HEX.forest900,
};

export const CROP_HEX: Record<Crop, string> = { cotton: HEX.forest600, hemp: HEX.wheat600 };

/** An area with the unit the server measured it in. */
export function area(value: number, unit: string, digits = 1): string {
  return `${formatNumber(value, digits)} ${unit}`;
}

/** A weight in kilograms, and in maunds too when the programme is cotton. */
export function mass(kg: number, unit: string): string {
  if (unit === 'maund') {
    return `${formatCompact(kg)} kg (${formatNumber(kg / KG_PER_MAUND, 1)} maunds)`;
  }
  if (unit === 't') return `${formatCompact(kg)} kg (${formatNumber(kg / KG_PER_TONNE, 2)} t)`;
  return `${formatCompact(kg)} kg`;
}

/** Tonnes, for a chart axis where kilograms would be unreadable. */
export function tonnes(kg: number): number {
  return Math.round((kg / KG_PER_TONNE) * 10) / 10;
}

export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return '-';
  return `${formatNumber(value, digits)}%`;
}

export function pluralise(count: number, singular: string, plural = `${singular}s`): string {
  return `${formatNumber(count)} ${count === 1 ? singular : plural}`;
}

/** 19 Oct, for a chart axis where the year is noise. */
export function shortDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

/** "4 minutes ago", "2 days ago": the activity feed reads better in relative time. */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '-';
  const seconds = Math.round((now.getTime() - then.getTime()) / 1000);
  if (seconds < 45) return 'just now';
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['minute', 60],
    ['hour', 3600],
    ['day', 86_400],
    ['week', 604_800],
    ['month', 2_629_800],
    ['year', 31_557_600],
  ];
  const formatter = new Intl.RelativeTimeFormat('en-GB', { numeric: 'auto' });
  let chosen: [Intl.RelativeTimeFormatUnit, number] = units[0]!;
  for (const unit of units) if (seconds >= unit[1]) chosen = unit;
  return formatter.format(-Math.round(seconds / chosen[1]), chosen[0]);
}
