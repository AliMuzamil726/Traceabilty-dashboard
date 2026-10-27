import { describe, expect, it } from 'vitest';
import { isRangeIncomplete, readFilters, toApiParams } from '../hooks/useDashboardFilters';
import { area, mass, percent, relativeTime } from '../lib/format';
import { toHref } from '../lib/links';

describe('filters from the address', () => {
  it('reads every control and falls back to safe defaults', () => {
    const f = readFilters(new URLSearchParams('crop=hemp&season=2025&range=7d&scope=all&module=5'));
    expect(f).toMatchObject({ crop: 'hemp', season: 2025, range: '7d', scope: 'all', module: 5 });

    const junk = readFilters(new URLSearchParams('crop=maize&season=abc&range=forever&scope=x&module=99'));
    expect(junk.crop).toBe('all');
    expect(junk.range).toBe('30d');
    expect(junk.scope).toBe('');
    expect(junk.module).toBeNull();
    expect(junk.season).toBe(new Date().getFullYear());
  });

  it('leaves scope to the server until the officer chooses', () => {
    expect(toApiParams(readFilters(new URLSearchParams(''))).scope).toBeUndefined();
    expect(toApiParams(readFilters(new URLSearchParams('scope=mine'))).scope).toBe('mine');
  });

  it('sends a custom range only when both ends are set', () => {
    const half = readFilters(new URLSearchParams('range=custom&from=2026-10-01'));
    expect(isRangeIncomplete(half)).toBe(true);
    expect(toApiParams(half)).toMatchObject({ range: '30d', from: undefined, to: undefined });

    const whole = readFilters(new URLSearchParams('range=custom&from=2026-10-01&to=2026-10-10'));
    expect(isRangeIncomplete(whole)).toBe(false);
    expect(toApiParams(whole)).toMatchObject({ range: 'custom', from: '2026-10-01', to: '2026-10-10' });
  });
});

describe('links into the modules', () => {
  it('keeps the path and the filters, dropping empty ones', () => {
    expect(toHref({ path: '/radar', params: { status: 'ready', crop: 'cotton', q: '' } })).toBe(
      '/radar?status=ready&crop=cotton',
    );
    expect(toHref({ path: '/fieldbook', params: {} })).toBe('/fieldbook');
  });
});

describe('units and wording', () => {
  it('writes the area in the unit the server measured', () => {
    expect(area(12.5, 'acre')).toBe('12.5 acre');
    expect(area(4, 'ha')).toBe('4 ha');
  });

  it('adds maunds for cotton and tonnes for hemp', () => {
    expect(mass(8000, 'maund')).toBe('8,000 kg (200 maunds)');
    expect(mass(2500, 't')).toBe('2,500 kg (2.5 t)');
  });

  it('formats a missing percentage as a dash', () => {
    expect(percent(null)).toBe('-');
    expect(percent(33.33, 1)).toBe('33.3%');
  });

  it('speaks of time relatively', () => {
    const now = new Date('2026-10-23T12:00:00Z');
    expect(relativeTime('2026-10-23T11:59:50Z', now)).toBe('just now');
    expect(relativeTime('2026-10-23T11:55:00Z', now)).toBe('5 minutes ago');
    expect(relativeTime('2026-10-21T12:00:00Z', now)).toBe('2 days ago');
  });
});
