import { describe, expect, it } from 'vitest';
import {
  kgText,
  maunds,
  netWeight,
  previewVariance,
  referenceWeight,
  validateAccept,
  validateReject,
} from '../lib/gate';

describe('net weight and reference', () => {
  it('subtracts tare from gross and needs both readings', () => {
    expect(netWeight(1020, 20)).toBe(1000);
    expect(netWeight(1000.555, 0.005)).toBe(1000.55);
    expect(netWeight(null, 20)).toBeNull();
    expect(netWeight(1020, null)).toBeNull();
  });

  it('prefers the field weight, then the pickup estimate', () => {
    expect(referenceWeight({ field_weight_kg: 990, estimated_quantity_kg: 2000 })).toEqual({ kg: 990, label: 'field weight' });
    expect(referenceWeight({ field_weight_kg: null, estimated_quantity_kg: 800 })).toEqual({ kg: 800, label: 'estimate' });
    expect(referenceWeight({ field_weight_kg: null, estimated_quantity_kg: null })).toBeNull();
  });
});

describe('variance preview follows the entry tolerances', () => {
  const load = { field_weight_kg: 1000, estimated_quantity_kg: 1200, variance_warn_pct: 3, variance_flag_pct: 5 };

  it.each([
    [1029.9, 2.99, 'ok'],
    [1030, 3, 'warn'],
    [1049.9, 4.99, 'warn'],
    [1050, 5, 'flag'],
    [950, -5, 'flag'],
  ])('%s kg against 1000 kg is %s%% (%s)', (net, pct, level) => {
    const v = previewVariance(net, load);
    expect(v).not.toBeNull();
    expect(v!.variancePct).toBe(pct);
    expect(v!.level).toBe(level);
  });

  it('falls back to the estimate and names it', () => {
    const v = previewVariance(1000, { ...load, field_weight_kg: null });
    expect(v).toMatchObject({ referenceKg: 1200, referenceLabel: 'estimate', variancePct: -16.67, level: 'flag' });
  });

  it('has nothing to compare without a reference, a positive net or thresholds', () => {
    expect(previewVariance(1000, { ...load, field_weight_kg: null, estimated_quantity_kg: null })).toBeNull();
    expect(previewVariance(0, load)).toBeNull();
    expect(previewVariance(null, load)).toBeNull();
    expect(previewVariance(1000, { ...load, variance_warn_pct: null })).toBeNull();
  });
});

describe('accept validation', () => {
  const load = { field_weight_kg: 1000, estimated_quantity_kg: null, variance_warn_pct: 3, variance_flag_pct: 5 };

  it('accepts a complete reading within the limits', () => {
    expect(validateAccept({ gross: 1000, tare: 20, moisture: 9, note: '' }, load)).toEqual({});
  });

  it('flags every missing or impossible reading', () => {
    const errors = validateAccept({ gross: null, tare: null, moisture: null, note: '' }, load);
    expect(Object.keys(errors).sort()).toEqual(['gross_weight_kg', 'moisture_pct', 'tare_weight_kg']);
  });

  it('requires the gross to exceed the tare', () => {
    expect(validateAccept({ gross: 20, tare: 20, moisture: 9, note: '' }, load).gross_weight_kg).toBeDefined();
  });

  it('needs a note only when the variance is flagged', () => {
    const flagged = validateAccept({ gross: 1080, tare: 20, moisture: 9, note: '' }, load);
    expect(flagged.note).toMatch(/differs by more than 5%/);
    expect(validateAccept({ gross: 1080, tare: 20, moisture: 9, note: 'Wet after rain' }, load)).toEqual({});
    expect(validateAccept({ gross: 1040, tare: 20, moisture: 9, note: '' }, load)).toEqual({});
  });
});

describe('reject validation', () => {
  it('wants a real reason, within 500 characters', () => {
    expect(validateReject('')).toMatch(/reason/i);
    expect(validateReject('  no  ')).toMatch(/reason/i);
    expect(validateReject('Spoiled crop')).toBeNull();
    expect(validateReject('x'.repeat(501))).toMatch(/500/);
  });
});

describe('readable weights', () => {
  it('shows cotton in kilograms and maunds, hemp in kilograms', () => {
    expect(maunds(4000)).toBe(100);
    expect(kgText(4000)).toBe('4,000 kg (100 maunds)');
    expect(kgText(4000, 'hemp')).toBe('4,000 kg');
    expect(kgText(null)).toBe('-');
  });
});
