import { describe, expect, it } from 'vitest';
import { actionsFor } from '../lib/status';
import { validateTransport } from '../lib/validation';
import { maunds, previewVariance } from '../lib/variance';

const T = { variance_warn_pct: 3, variance_flag_pct: 5 };

describe('variance preview mirrors the server', () => {
  it.each([
    [1029.9, 2.99, 'ok'],
    [1030, 3, 'warn'],
    [1049.9, 4.99, 'warn'],
    [1050, 5, 'flag'],
    [950, -5, 'flag'],
  ])('%s kg against 1000 kg is %s%% (%s)', (weight, pct, level) => {
    const v = previewVariance(weight, 1000, null, T);
    expect(v.variancePct).toBe(pct);
    expect(v.level).toBe(level);
  });

  it('prefers the field weight, then the estimate', () => {
    expect(previewVariance(1000, 990, 2000, T).reference).toBe('field_weight');
    expect(previewVariance(1000, null, 800, T)).toMatchObject({ reference: 'estimate', variancePct: 25, level: 'flag' });
    expect(previewVariance(1000, null, null, T).level).toBeNull();
    expect(previewVariance(null, 1000, null, T).level).toBeNull();
  });

  it('converts maunds', () => {
    expect(maunds(4000)).toBe(100);
  });
});

describe('Schedule validation', () => {
  const ok = { site_id: 's', scheduled_date: '2026-10-23', driver_name: 'Akram Ali', driver_phone: '0301 7654321', vehicle_no: 'mna-1234' };

  it('accepts a complete Pakistani schedule', () => {
    expect(validateTransport(ok, 'PK', '2026-10-22')).toEqual({});
  });

  it('flags every missing or wrong answer', () => {
    const errors = validateTransport({ site_id: '', scheduled_date: '2026-10-21', driver_name: 'A', driver_phone: '07700 900123', vehicle_no: '!' }, 'PK', '2026-10-22');
    expect(Object.keys(errors).sort()).toEqual(['driver_name', 'driver_phone', 'scheduled_date', 'site_id', 'vehicle_no']);
  });

  it('checks phones against the site country', () => {
    expect(validateTransport({ ...ok, driver_phone: '07700 900123' }, 'GB', '2026-10-22')).toEqual({});
    expect(validateTransport({ ...ok, driver_phone: '0301 7654321' }, 'GB', '2026-10-22').driver_phone).toBeDefined();
  });
});

describe('status-dependent actions', () => {
  it.each([
    ['scheduled', { edit: true, dispatch: true, receive: false, cancel: true, correct: false }],
    ['in_transit', { edit: false, dispatch: false, receive: true, cancel: true, correct: false }],
    ['delivered', { edit: false, dispatch: false, receive: false, cancel: false, correct: false }],
    ['cancelled', { edit: false, dispatch: false, receive: false, cancel: false, correct: false }],
  ] as const)('%s offers only its own actions', (status, expected) => {
    expect(actionsFor(status, true, false)).toEqual(expected);
  });

  it('administrators may correct a delivered record; read-only rows offer nothing else', () => {
    expect(actionsFor('delivered', false, true).correct).toBe(true);
    expect(Object.values(actionsFor('scheduled', false, false)).some(Boolean)).toBe(false);
  });
});
