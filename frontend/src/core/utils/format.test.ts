import { describe, expect, it } from 'vitest';
import {
  countryName,
  formatCompact,
  formatCoordinate,
  formatDate,
  formatDateTime,
  formatDecimal,
  formatNumber,
  formatPercent,
  formatWithUnit,
  initials,
  pluralize,
  roleLabel,
} from './format';

describe('format', () => {
  it('formats numbers with grouping and an empty dash', () => {
    expect(formatNumber(1234567)).toBe('1,234,567');
    expect(formatNumber(12.345, 2)).toBe('12.35');
    expect(formatNumber(null)).toBe('-');
    expect(formatNumber(Number.NaN)).toBe('-');
  });

  it('formats decimals with fixed digits', () => {
    expect(formatDecimal(2)).toBe('2.00');
    expect(formatDecimal(1234.5, 1)).toBe('1,234.5');
  });

  it('formats percentages and compact counts', () => {
    expect(formatPercent(0.256)).toBe('26%');
    expect(formatPercent(0.256, 1)).toBe('25.6%');
    expect(formatCompact(9999)).toBe('9,999');
    expect(formatCompact(12_500)).toBe('12.5k');
    expect(formatCompact(3_100_000)).toBe('3.1M');
  });

  it('formats values with units', () => {
    expect(formatWithUnit(3.456, 'acres')).toBe('3.46 acres');
    expect(formatWithUnit(undefined, 'ha')).toBe('-');
  });

  it('formats dates in en-GB style', () => {
    expect(formatDate('2026-10-19T08:00:00Z')).toBe('19 Oct 2026');
    expect(formatDate('not a date')).toBe('-');
    expect(formatDate(null)).toBe('-');
    expect(formatDateTime(new Date(2026, 9, 19, 14, 5))).toBe('19 Oct 2026, 14:05');
  });

  it('formats coordinates with fixed precision', () => {
    expect(formatCoordinate(30.1575)).toBe('30.157500');
    expect(formatCoordinate(71.5249, 4)).toBe('71.5249');
  });

  it('builds initials', () => {
    expect(initials('Muhammad Imran Khan')).toBe('MK');
    expect(initials('oliver')).toBe('O');
    expect(initials('  ')).toBe('?');
    expect(initials(null)).toBe('?');
  });

  it('pluralizes and labels', () => {
    expect(pluralize(1, 'farmer')).toBe('1 farmer');
    expect(pluralize(1200, 'farmer')).toBe('1,200 farmers');
    expect(pluralize(2, 'batch', 'batches')).toBe('2 batches');
    expect(countryName('pk')).toBe('Pakistan');
    expect(countryName('GB')).toBe('United Kingdom');
    expect(roleLabel('admin')).toBe('Administrator');
    expect(roleLabel('officer')).toBe('Field officer');
  });
});
