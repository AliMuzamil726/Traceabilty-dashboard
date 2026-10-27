import { describe, expect, it } from 'vitest';
import {
  CROP_COUNTRY,
  formatHempId,
  formatIdNumber,
  formatLatLng,
  formatPhone,
  formatPkPhone,
  formatPostcode,
  formatUkPhone,
} from '../format';

describe('CNIC mask', () => {
  it('formats digits as they are typed', () => {
    expect(formatIdNumber('3', 'cotton')).toBe('3');
    expect(formatIdNumber('35202', 'cotton')).toBe('35202');
    expect(formatIdNumber('352021', 'cotton')).toBe('35202-1');
    expect(formatIdNumber('3520212345671', 'cotton')).toBe('35202-1234567-1');
  });

  it('reformats a pasted unformatted number', () => {
    expect(formatIdNumber('3520212345671', 'cotton')).toBe('35202-1234567-1');
  });

  it('reformats a pasted already formatted number unchanged', () => {
    expect(formatIdNumber('35202-1234567-1', 'cotton')).toBe('35202-1234567-1');
  });

  it('ignores letters and punctuation in a paste', () => {
    expect(formatIdNumber('35202 1234567 1', 'cotton')).toBe('35202-1234567-1');
    expect(formatIdNumber('abc35202def1234567ghi1', 'cotton')).toBe('35202-1234567-1');
  });

  it('never grows past 13 digits', () => {
    expect(formatIdNumber('352021234567199999', 'cotton')).toBe('35202-1234567-1');
  });

  it('is stable: formatting its own output changes nothing', () => {
    const once = formatIdNumber('3520212345671', 'cotton');
    expect(formatIdNumber(once, 'cotton')).toBe(once);
  });
});

describe('hemp ID grouping', () => {
  it('groups digits in threes', () => {
    expect(formatHempId('123456789')).toBe('123 456 789');
    // A trailing single digit merges back, so there is never a group of one.
    expect(formatHempId('1234')).toBe('1234');
    expect(formatHempId('12345')).toBe('123 45');
  });

  it('merges a trailing single digit into the group before it', () => {
    expect(formatHempId('1234567890123')).toBe('123 456 789 0123');
  });

  it('never leaves a group of one, at any accepted length', () => {
    for (let length = 9; length <= 13; length += 1) {
      const groups = formatHempId('1'.repeat(length)).split(' ');
      expect(groups[groups.length - 1]!.length).toBeGreaterThan(1);
    }
  });

  it('stops at 13 digits and ignores non-digits', () => {
    expect(formatHempId('12345678901234567')).toBe('123 456 789 0123');
    expect(formatHempId('12-34 56.789')).toBe('123 456 789');
  });

  it('is empty for empty input', () => {
    expect(formatHempId('')).toBe('');
  });
});

describe('Pakistani phone normalisation', () => {
  it.each([
    ['03001234567', '0300-1234567'],
    ['0300-1234567', '0300-1234567'],
    ['+92 300 1234567', '0300-1234567'],
    ['+923001234567', '0300-1234567'],
    ['0092 300 1234567', '0300-1234567'],
  ])('turns %s into %s', (input, expected) => {
    expect(formatPkPhone(input)).toBe(expected);
  });

  it('formats progressively while typing', () => {
    expect(formatPkPhone('03')).toBe('03');
    // No trailing separator while typing: the dash appears with the digit after it.
    expect(formatPkPhone('0300')).toBe('0300');
    expect(formatPkPhone('03001')).toBe('0300-1');
    expect(formatPkPhone('030012')).toBe('0300-12');
  });

  it('is stable and routed by crop', () => {
    const once = formatPkPhone('+92 300 1234567');
    expect(formatPkPhone(once)).toBe(once);
    expect(formatPhone('+92 300 1234567', 'cotton')).toBe('0300-1234567');
  });
});

describe('UK phone normalisation', () => {
  it.each([
    ['07700900123', '07700 900123'],
    ['07700 900123', '07700 900123'],
    ['+44 7700 900123', '07700 900123'],
    ['+447700900123', '07700 900123'],
    ['0044 7700 900123', '07700 900123'],
  ])('turns %s into %s', (input, expected) => {
    expect(formatUkPhone(input)).toBe(expected);
  });

  it('is stable and routed by crop', () => {
    const once = formatUkPhone('+44 7700 900123');
    expect(formatUkPhone(once)).toBe(once);
    expect(formatPhone('+44 7700 900123', 'hemp')).toBe('07700 900123');
  });
});

describe('postcode formatting', () => {
  it.each([
    ['ln43qp', 'LN4 3QP'],
    ['LN4 3QP', 'LN4 3QP'],
    ['cb236dp', 'CB23 6DP'],
    ['m11ae', 'M1 1AE'],
    ['sw1a1aa', 'SW1A 1AA'],
  ])('turns %s into %s', (input, expected) => {
    expect(formatPostcode(input)).toBe(expected);
  });

  it('leaves a part-typed postcode alone until it is long enough to split', () => {
    expect(formatPostcode('ln')).toBe('LN');
    expect(formatPostcode('ln4')).toBe('LN4');
  });

  it('is stable', () => {
    const once = formatPostcode('ln43qp');
    expect(formatPostcode(once)).toBe(once);
  });
});

describe('crop to country', () => {
  it('maps cotton to Pakistan and hemp to the United Kingdom', () => {
    expect(CROP_COUNTRY.cotton).toBe('PK');
    expect(CROP_COUNTRY.hemp).toBe('GB');
  });
});

describe('coordinates', () => {
  it('quotes six decimal places by default', () => {
    expect(formatLatLng(30.1575, 71.5249)).toBe('30.157500, 71.524900');
    expect(formatLatLng(30.1575, 71.5249, 2)).toBe('30.16, 71.52');
  });
});
