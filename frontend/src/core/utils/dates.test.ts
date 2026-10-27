import { describe, expect, it } from 'vitest';
import { addDays, daysBetween, parseIsoDate, relativeDays, toIsoDate } from './dates';

describe('dates', () => {
  it('round-trips ISO dates in local time', () => {
    const d = parseIsoDate('2026-02-28');
    expect(d).not.toBeNull();
    expect(toIsoDate(d as Date)).toBe('2026-02-28');
    expect(parseIsoDate('2026-02-30')).toBeNull();
    expect(parseIsoDate('19/10/2026')).toBeNull();
  });

  it('counts and describes days', () => {
    const now = new Date(2026, 9, 19);
    expect(daysBetween(now, addDays(now, 3))).toBe(3);
    expect(relativeDays(addDays(now, 3), now)).toBe('in 3 days');
    expect(relativeDays(addDays(now, -2), now)).toBe('2 days ago');
    expect(relativeDays(now, now)).toBe('today');
  });
});
