/**
 * Display helpers for Module 2.
 *
 * These live in a plain module rather than beside a component so the masks can be
 * unit tested, and so importing one never drags a React component along with it.
 */

import { formatCnic, normalizeIdNumber } from '@/core/utils/validators';
import type { Crop } from './api/types';

export const HEMP_ID_MAX_DIGITS = 13;

/**
 * Group a hemp ID number in threes, merging a trailing single digit into the group
 * before it so the last group is never one lonely character.
 *
 * ``123456789`` -> ``123 456 789``; ``1234567890123`` -> ``123 456 789 0123``.
 * This mirrors backend/module_2/services/validators.py::format_hemp_id.
 */
export function formatHempId(value: string): string {
  const digits = normalizeIdNumber(value).replace(/\D/g, '').slice(0, HEMP_ID_MAX_DIGITS);
  if (!digits) return '';
  const groups: string[] = [];
  for (let i = 0; i < digits.length; i += 3) groups.push(digits.slice(i, i + 3));
  if (groups.length > 1 && (groups[groups.length - 1] as string).length === 1) {
    const last = groups.pop() as string;
    groups[groups.length - 1] = `${groups[groups.length - 1] as string}${last}`;
  }
  return groups.join(' ');
}

/** Format an ID number as the officer types it, according to the crop programme. */
export function formatIdNumber(value: string, crop: Crop): string {
  return crop === 'cotton' ? formatCnic(value) : formatHempId(value);
}

/**
 * Format a Pakistani mobile number as ``0300-1234567`` while it is typed, accepting
 * the ``+92`` and ``0092`` forms and the local one.
 */
export function formatPkPhone(value: string): string {
  let digits = value.replace(/\D/g, '');
  if (digits.startsWith('0092')) digits = digits.slice(4);
  else if (digits.startsWith('92') && digits.length > 10) digits = digits.slice(2);
  else if (digits.startsWith('0')) digits = digits.slice(1);
  digits = digits.slice(0, 10);
  if (!digits) return '';
  if (digits.length <= 3) return `0${digits}`;
  return `0${digits.slice(0, 3)}-${digits.slice(3)}`;
}

/** Format a UK mobile number as ``07700 900123`` while it is typed. */
export function formatUkPhone(value: string): string {
  let digits = value.replace(/\D/g, '');
  if (digits.startsWith('0044')) digits = digits.slice(4);
  else if (digits.startsWith('44') && digits.length > 10) digits = digits.slice(2);
  else if (digits.startsWith('0')) digits = digits.slice(1);
  digits = digits.slice(0, 10);
  if (!digits) return '';
  if (digits.length <= 4) return `0${digits}`;
  return `0${digits.slice(0, 4)} ${digits.slice(4)}`;
}

/**
 * Is this a UK *mobile* number?
 *
 * `isUkPhone` in core accepts any 11 digit UK number, which is right for a general
 * phone field. The farmer form needs a mobile, because that is what the server
 * accepts, and a form that passes what the server will reject is worse than no
 * validation at all.
 */
export function isUkMobile(value: string): boolean {
  const digits = value.replace(/\D/g, '');
  const local = digits.startsWith('0044')
    ? digits.slice(4)
    : digits.startsWith('44') && digits.length === 12
      ? digits.slice(2)
      : digits.startsWith('0')
        ? digits.slice(1)
        : digits;
  return local.length === 10 && local.startsWith('7');
}

export function formatPhone(value: string, crop: Crop): string {
  return crop === 'cotton' ? formatPkPhone(value) : formatUkPhone(value);
}

/** Uppercase a UK postcode and put the single space before the final three characters. */
export function formatPostcode(value: string): string {
  const compact = value.replace(/\s+/g, '').toUpperCase().slice(0, 7);
  if (compact.length <= 3) return compact;
  return `${compact.slice(0, compact.length - 3)} ${compact.slice(compact.length - 3)}`;
}

/** The country each crop programme runs in: cotton in Pakistan, hemp in the UK. */
export const CROP_COUNTRY: Record<Crop, string> = { cotton: 'PK', hemp: 'GB' };

export const CROP_LABEL: Record<Crop, string> = { cotton: 'Cotton', hemp: 'Hemp' };

export function countryForCrop(crop: Crop): string {
  return CROP_COUNTRY[crop];
}

/** Coordinates at the precision a field boundary is worth quoting to. */
export function formatLatLng(lat: number, lng: number, digits = 6): string {
  return `${lat.toFixed(digits)}, ${lng.toFixed(digits)}`;
}
