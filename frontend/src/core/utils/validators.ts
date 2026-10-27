/**
 * Pure validation helpers. Each returns true when valid. Zod schemas in modules wrap
 * these with user-facing messages.
 */

export function isBlank(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === 'string' && value.trim() === '');
}

export function isRequired(value: unknown): boolean {
  return !isBlank(value);
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function isEmail(value: string): boolean {
  return EMAIL.test(value.trim());
}

/** Strip spaces, dashes and dots and upper-case: the form used for uniqueness checks. */
export function normalizeIdNumber(value: string): string {
  return value.replace(/[\s\-.]/g, '').toUpperCase();
}

/** Pakistani CNIC: 13 digits, with or without dashes (12345-1234567-1). */
export function isCnic(value: string): boolean {
  const trimmed = value.trim();
  if (!/^(\d{5}-\d{7}-\d|\d{13})$/.test(trimmed)) return false;
  return normalizeIdNumber(trimmed).length === 13;
}

/** Format 13 CNIC digits as 12345-1234567-1. */
export function formatCnic(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 13);
  if (digits.length <= 5) return digits;
  if (digits.length <= 12) return `${digits.slice(0, 5)}-${digits.slice(5)}`;
  return `${digits.slice(0, 5)}-${digits.slice(5, 12)}-${digits.slice(12)}`;
}

/** Pakistani mobile: 03XXXXXXXXX or +923XXXXXXXXX (spaces and dashes allowed). */
export function isPkMobile(value: string): boolean {
  const compact = value.replace(/[\s-]/g, '');
  return /^(03\d{9}|\+923\d{9}|00923\d{9})$/.test(compact);
}

/** UK phone: 0 followed by 10 digits, or +44 followed by 10 digits. */
export function isUkPhone(value: string): boolean {
  const compact = value.replace(/[\s\-()]/g, '');
  return /^(0\d{10}|\+44\d{10})$/.test(compact);
}

export function isPhoneForCountry(value: string, country: string): boolean {
  if (country.toUpperCase() === 'PK') return isPkMobile(value);
  if (country.toUpperCase() === 'GB') return isUkPhone(value);
  return /^\+?\d{7,15}$/.test(value.replace(/[\s\-()]/g, ''));
}

const UK_POSTCODE = /^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$/i;

export function isUkPostcode(value: string): boolean {
  return UK_POSTCODE.test(value.trim());
}

export function isLatitude(value: number): boolean {
  return Number.isFinite(value) && value >= -90 && value <= 90;
}

export function isLongitude(value: number): boolean {
  return Number.isFinite(value) && value >= -180 && value <= 180;
}

export function isPositiveNumber(value: number): boolean {
  return Number.isFinite(value) && value > 0;
}

export function isInRange(value: number, min: number, max: number): boolean {
  return Number.isFinite(value) && value >= min && value <= max;
}
