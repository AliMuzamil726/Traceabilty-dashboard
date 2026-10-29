import { describe, expect, it } from 'vitest';
import {
  TEHSIL_OTHER,
  defaultsForCrop,
  emptyFarmerForm,
  farmerFormSchema,
  type FarmerFormValues,
} from '../api/schemas';

const COTTON: FarmerFormValues = {
  ...emptyFarmerForm,
  crop: 'cotton',
  id_number: '35202-1234567-1',
  name: 'Muhammad Imran',
  father_name: 'Ghulam Rasool',
  phone: '0300-1234567',
  province_code: 'PK-PB',
  district_code: 'PK-PB-MUL',
  tehsil_code: 'PK-PB-MUL-T01',
  village: 'Basti Malook',
  field_office_id: 'office-1',
  variety: 'fh-142',
  tenure: 'owner',
  previous_crop: 'wheat',
};

const HEMP: FarmerFormValues = {
  ...emptyFarmerForm,
  crop: 'hemp',
  id_number: '123 456 789',
  name: 'Sarah Whitfield',
  farm_name: 'Fen End Farm',
  phone: '07700 900123',
  home_office_licence_no: 'HO-HEMP-2026-0041',
  postcode: 'LN4 3QP',
  field_office_id: 'office-2',
  variety: 'futura_75',
  tenure: 'owner_occupier',
  previous_crop: 'winter_wheat',
};

/** Field paths that failed validation. */
function errorPaths(values: FarmerFormValues): string[] {
  const result = farmerFormSchema.safeParse(values);
  if (result.success) return [];
  return result.error.issues.map((issue) => issue.path.join('.')).sort();
}

describe('cotton form', () => {
  it('accepts a complete form', () => {
    expect(errorPaths(COTTON)).toEqual([]);
  });

  it('requires the cotton fields', () => {
    expect(errorPaths({ ...emptyFarmerForm, crop: 'cotton' })).toEqual([
      'district_code',
      'father_name',
      'field_office_id',
      'id_number',
      'name',
      'phone',
      'province_code',
      'tehsil_code',
      'tenure',
      'variety',
      'village',
    ]);
  });

  it('rejects a CNIC that is not 13 digits', () => {
    expect(errorPaths({ ...COTTON, id_number: '35202-123456-1' })).toEqual(['id_number']);
    expect(errorPaths({ ...COTTON, id_number: '352021234567' })).toEqual(['id_number']);
  });

  it('accepts a CNIC with or without dashes', () => {
    expect(errorPaths({ ...COTTON, id_number: '3520212345671' })).toEqual([]);
  });

  it('rejects a phone that is not a Pakistani mobile, and requires one', () => {
    expect(errorPaths({ ...COTTON, phone: '0400-1234567' })).toEqual(['phone']);
    expect(errorPaths({ ...COTTON, phone: '' })).toEqual(['phone']);
  });

  it('rejects names with digits or symbols', () => {
    expect(errorPaths({ ...COTTON, name: 'Imran99' })).toEqual(['name']);
    expect(errorPaths({ ...COTTON, name: 'Imran@Khan' })).toEqual(['name']);
  });

  it('accepts a name in a non-Latin script', () => {
    expect(errorPaths({ ...COTTON, name: 'محمد عمران' })).toEqual([]);
  });

  it('enforces the name length bounds', () => {
    expect(errorPaths({ ...COTTON, name: 'ab' })).toEqual(['name']);
    expect(errorPaths({ ...COTTON, name: 'a'.repeat(61) })).toEqual(['name']);
  });

  it('accepts a typed tehsil when Other is chosen', () => {
    expect(
      errorPaths({ ...COTTON, tehsil_code: TEHSIL_OTHER, tehsil_name: 'Some New Tehsil' }),
    ).toEqual([]);
  });

  it('asks for the typed name when Other is chosen and left blank', () => {
    expect(errorPaths({ ...COTTON, tehsil_code: TEHSIL_OTHER, tehsil_name: '' })).toEqual([
      'tehsil_name',
    ]);
  });

  it('asks for a tehsil when neither a choice nor a typed name is given', () => {
    expect(errorPaths({ ...COTTON, tehsil_code: '', tehsil_name: '' })).toEqual(['tehsil_code']);
  });

  it('requires a village of at least two characters', () => {
    expect(errorPaths({ ...COTTON, village: 'a' })).toEqual(['village']);
    expect(errorPaths({ ...COTTON, village: '' })).toEqual(['village']);
  });

  it('does not ask for any hemp field', () => {
    const paths = errorPaths({ ...COTTON, farm_name: '', postcode: '', home_office_licence_no: '' });
    expect(paths).toEqual([]);
  });

  it('still requires the crop details', () => {
    expect(errorPaths({ ...COTTON, variety: '', tenure: '' })).toEqual(['tenure', 'variety']);
  });

  it('treats the previous crop as optional', () => {
    expect(errorPaths({ ...COTTON, previous_crop: '' })).toEqual([]);
  });
});

describe('hemp form', () => {
  it('accepts a complete form', () => {
    expect(errorPaths(HEMP)).toEqual([]);
  });

  it('requires the hemp fields', () => {
    expect(errorPaths({ ...emptyFarmerForm, crop: 'hemp' })).toEqual([
      'farm_name',
      'field_office_id',
      'home_office_licence_no',
      'id_number',
      'name',
      'postcode',
      'tenure',
      'variety',
    ]);
  });

  it('accepts 9 to 13 digits and rejects anything outside that', () => {
    expect(errorPaths({ ...HEMP, id_number: '123456789' })).toEqual([]);
    expect(errorPaths({ ...HEMP, id_number: '1234567890123' })).toEqual([]);
    expect(errorPaths({ ...HEMP, id_number: '12345678' })).toEqual(['id_number']);
    expect(errorPaths({ ...HEMP, id_number: '12345678901234' })).toEqual(['id_number']);
  });

  it('rejects a non-numeric ID number', () => {
    expect(errorPaths({ ...HEMP, id_number: 'ABC123456' })).toEqual(['id_number']);
  });

  it('rejects an invalid postcode', () => {
    expect(errorPaths({ ...HEMP, postcode: 'NOPE' })).toEqual(['postcode']);
  });

  it('rejects a phone that is not a UK mobile, and allows a blank one', () => {
    expect(errorPaths({ ...HEMP, phone: '01632 960123' })).toEqual(['phone']);
    expect(errorPaths({ ...HEMP, phone: '' })).toEqual([]);
  });

  it('checks the licence number shape and length', () => {
    expect(errorPaths({ ...HEMP, home_office_licence_no: 'HO_12345' })).toEqual([
      'home_office_licence_no',
    ]);
    expect(errorPaths({ ...HEMP, home_office_licence_no: 'HO12' })).toEqual([
      'home_office_licence_no',
    ]);
    expect(errorPaths({ ...HEMP, home_office_licence_no: 'X'.repeat(31) })).toEqual([
      'home_office_licence_no',
    ]);
  });

  it('does not ask for the county or region while the postcode resolves', () => {
    expect(errorPaths({ ...HEMP, county: '', region: '', postcode_manual: false })).toEqual([]);
  });

  it('asks for the county and region only when the lookup failed', () => {
    expect(errorPaths({ ...HEMP, county: '', region: '', postcode_manual: true })).toEqual([
      'county',
      'region',
    ]);
    expect(
      errorPaths({
        ...HEMP,
        county: 'Lincolnshire',
        region: 'East Midlands',
        postcode_manual: true,
      }),
    ).toEqual([]);
  });

  it('does not ask for any cotton field', () => {
    expect(errorPaths({ ...HEMP, father_name: '', village: '', province_code: '' })).toEqual([]);
  });
});

describe('defaults', () => {
  it('start empty for the chosen crop', () => {
    expect(defaultsForCrop('cotton').crop).toBe('cotton');
    expect(defaultsForCrop('hemp').crop).toBe('hemp');
    expect(defaultsForCrop('hemp').id_number).toBe('');
    expect(defaultsForCrop('hemp').postcode_manual).toBe(false);
  });
});
