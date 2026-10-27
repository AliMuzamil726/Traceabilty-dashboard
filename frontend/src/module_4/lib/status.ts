/**
 * How each readiness bucket looks. The rules that decide a bucket live in the backend
 * (module_4/services/readiness.py); this file only maps a bucket to its colours.
 * Everything stays inside the two-colour system.
 */
import type { Bucket, PickupState } from '../api/types';

export const BUCKET_ORDER: Bucket[] = ['no_sowing_data', 'growing', 'approaching', 'ready', 'harvested'];

export const BUCKET_LABEL: Record<Bucket, string> = {
  no_sowing_data: 'No sowing data',
  growing: 'Growing',
  approaching: 'Approaching',
  ready: 'Ready',
  harvested: 'Harvested',
};

/** Tailwind classes for pills and swatches. */
export const BUCKET_CLASSES: Record<Bucket, { pill: string; dot: string }> = {
  no_sowing_data: { pill: 'border-line bg-surface text-muted', dot: 'bg-line' },
  growing: { pill: 'border-line bg-canvas text-muted', dot: 'bg-muted' },
  approaching: { pill: 'border-wheat-300 bg-wheat-50 text-ink', dot: 'bg-wheat-300' },
  ready: { pill: 'border-forest-600 bg-forest-600 text-white', dot: 'bg-forest-600' },
  harvested: { pill: 'border-forest-900 bg-forest-900 text-white', dot: 'bg-forest-900' },
};

/** Hex values for Leaflet and Recharts, which take colour strings (brand tokens only). */
export const HEX = {
  line: '#E3E6DE',
  muted: '#5B675F',
  wheat300: '#E3C479',
  wheat500: '#C79A2E',
  wheat600: '#A67C1F',
  forest600: '#25774A',
  forest700: '#1D6039',
  forest900: '#10331F',
  surface: '#FFFFFF',
} as const;

export const BUCKET_HEX: Record<Bucket, string> = {
  no_sowing_data: HEX.line,
  growing: HEX.muted,
  approaching: HEX.wheat300,
  ready: HEX.forest600,
  harvested: HEX.forest900,
};

export const PICKUP_LABEL: Record<PickupState, string> = {
  not_requested: 'Not requested',
  requested: 'Requested',
  scheduled: 'Scheduled',
  delivered: 'Delivered',
};
