import { describe, expect, it } from 'vitest';
import { computeValue, initialValues, isVisible, missingRequired, payloadFor, stepTotals, summarise } from '../lib/schemaLogic';
import { cotton, hemp, step } from './fixtures';

const field = (s: ReturnType<typeof step>, key: string) => s.fields.find((f) => f.key === key)!;

describe('schema logic mirrors the backend', () => {
  it('evaluates in and not_in conditions', () => {
    const irrigation = step(cotton, 'irrigation');
    expect(isVisible(field(irrigation, 'diesel_used'), { source: 'tubewell_diesel' })).toBe(true);
    expect(isVisible(field(irrigation, 'diesel_used'), { source: 'canal' })).toBe(false);
    const prep = step(cotton, 'land_preparation');
    expect(isVisible(field(prep, 'diesel_per_pass'), {})).toBe(true);
    expect(isVisible(field(prep, 'diesel_per_pass'), { machinery_type: 'manual' })).toBe(false);
  });

  it('computes counts, day spans and products', () => {
    const retting = step(hemp, 'retting');
    expect(computeValue(field(retting, 'number_of_turns'), { turning_dates: ['2026-08-01', '2026-08-05', null] })).toBe(2);
    expect(computeValue(field(retting, 'days_in_swath'), { retting_start: '2026-08-01', retting_end: '2026-08-14' })).toBe(13);
    expect(computeValue(field(step(hemp, 'baling'), 'total_straw_weight'), { number_of_bales: 20 })).toBeNull();
  });

  it('starts from server defaults and keeps read-only defaults fixed', () => {
    const info = step(hemp, 'field_info');
    const values = initialValues(info, { 'field.area_ha': 4.2, 'farmer.licence': 'HO-1' }, {
      entry_index: 0, data: { licence_no: 'typed', area_drilled: 3.9 }, completed: true, updated_at: '', updated_by: null,
    });
    expect(values.licence_no).toBe('HO-1');
    expect(values.area_drilled).toBe(3.9);
  });

  it('sends only visible, answered, non-computed fields', () => {
    const irrigation = step(cotton, 'irrigation');
    expect(payloadFor(irrigation, { source: 'canal', diesel_used: 5, duration: 3, method: '' })).toEqual({ source: 'canal', duration: 3 });
  });

  it('lists unanswered required fields', () => {
    expect(missingRequired(step(cotton, 'energy'), {})).toEqual(['total_diesel', 'grid_electricity']);
  });

  it('summarises with list labels and totals', () => {
    const harvest = step(cotton, 'harvest');
    const text = summarise(harvest, { picking_number: '1st', picking_date: '2026-10-01', yield: 12 }, (_, v) => `<${v}>`);
    expect(text).toBe('<1st> picking on 2026-10-01, 12 maunds per acre');
    const totals = stepTotals(step(cotton, 'nutrient_management'), [{ quantity: 50, n_content: 46 }, { quantity: 100, n_content: 18 }]);
    expect(totals.map((t) => t.value)).toEqual(['2', '150 kg per acre', '41 kg N per acre']);
  });
});
