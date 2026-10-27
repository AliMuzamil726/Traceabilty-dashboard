import { describe, expect, it } from 'vitest';
import {
  formatCnic,
  isBlank,
  isCnic,
  isEmail,
  isInRange,
  isLatitude,
  isLongitude,
  isPhoneForCountry,
  isPkMobile,
  isPositiveNumber,
  isRequired,
  isUkPhone,
  isUkPostcode,
  normalizeIdNumber,
} from './validators';

describe('validators', () => {
  it('detects blank and required values', () => {
    expect(isBlank('  ')).toBe(true);
    expect(isBlank(null)).toBe(true);
    expect(isBlank(0)).toBe(false);
    expect(isRequired('x')).toBe(true);
    expect(isRequired(undefined)).toBe(false);
  });

  it('validates email', () => {
    expect(isEmail('a.b@sawie.example')).toBe(true);
    expect(isEmail('nope@')).toBe(false);
    expect(isEmail('a b@c.de')).toBe(false);
  });

  it('normalises and validates CNIC', () => {
    expect(normalizeIdNumber('36302-1234567-1')).toBe('3630212345671');
    expect(normalizeIdNumber(' ab 12.3 ')).toBe('AB123');
    expect(isCnic('36302-1234567-1')).toBe(true);
    expect(isCnic('3630212345671')).toBe(true);
    expect(isCnic('36302-123456-1')).toBe(false);
    expect(isCnic('3630-21234567-1')).toBe(false);
    expect(formatCnic('3630212345671')).toBe('36302-1234567-1');
    expect(formatCnic('36302')).toBe('36302');
    expect(formatCnic('363021234')).toBe('36302-1234');
  });

  it('validates phone numbers per country', () => {
    expect(isPkMobile('0300 1234567')).toBe(true);
    expect(isPkMobile('+92 300 1234567')).toBe(true);
    expect(isPkMobile('0400 1234567')).toBe(false);
    expect(isUkPhone('07700 900123')).toBe(true);
    expect(isUkPhone('+44 7700 900123')).toBe(true);
    expect(isUkPhone('7700900123')).toBe(false);
    expect(isPhoneForCountry('03001234567', 'pk')).toBe(true);
    expect(isPhoneForCountry('+923001234567', 'GB')).toBe(false);
  });

  it('validates UK postcodes', () => {
    expect(isUkPostcode('HP18 0XB')).toBe(true);
    expect(isUkPostcode('cb21ab')).toBe(true);
    expect(isUkPostcode('12345')).toBe(false);
  });

  it('validates coordinates and numbers', () => {
    expect(isLatitude(30.19)).toBe(true);
    expect(isLatitude(91)).toBe(false);
    expect(isLongitude(-180)).toBe(true);
    expect(isLongitude(Number.NaN)).toBe(false);
    expect(isPositiveNumber(0)).toBe(false);
    expect(isPositiveNumber(0.1)).toBe(true);
    expect(isInRange(5, 1, 5)).toBe(true);
    expect(isInRange(6, 1, 5)).toBe(false);
  });
});
