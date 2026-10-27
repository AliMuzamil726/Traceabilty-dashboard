import { describe, expect, it } from 'vitest';
import { acresToM2, convertArea, convertMass, kgToMaunds, m2ToAcres, m2ToHectares, unitsForCrop } from './units';

describe('units', () => {
  it('converts area', () => {
    expect(m2ToAcres(4046.8564224)).toBeCloseTo(1, 10);
    expect(acresToM2(2)).toBeCloseTo(8093.7128448, 6);
    expect(m2ToHectares(25_000)).toBe(2.5);
    expect(convertArea(10_000, 'ha')).toBe(1);
    expect(convertArea(10, 'm2')).toBe(10);
  });

  it('converts mass', () => {
    expect(kgToMaunds(400)).toBe(10);
    expect(convertMass(2500, 't')).toBe(2.5);
  });

  it('chooses units per crop programme', () => {
    expect(unitsForCrop('cotton')).toEqual({ area: 'acre', mass: 'maund' });
    expect(unitsForCrop('hemp')).toEqual({ area: 'ha', mass: 't' });
  });
});
