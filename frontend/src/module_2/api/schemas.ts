/**
 * Validation for the farmer form.
 *
 * One schema covers both crop programmes. The alternative, a schema per crop, forces
 * the form to swap its value shape when the crop changes, which react-hook-form cannot
 * do without losing the fields the two programmes share. Instead the values are a flat
 * superset and `superRefine` applies only the rules of the chosen crop, so each error
 * still lands on its own field.
 *
 * The server validates all of this again (backend/module_2/services/validators.py).
 * These rules exist to answer before a round trip, not instead of one.
 */

import { z } from 'zod';
import { isCnic, isPkMobile, isUkPostcode, normalizeIdNumber } from '@/core/utils/validators';
import { isUkMobile } from '../format';
import type { Crop } from './types';

export const HEMP_ID_MIN_DIGITS = 9;
export const HEMP_ID_MAX_DIGITS = 13;

// JavaScript's \\w is ASCII only even under the /u flag, so an Urdu or Arabic name
// would be rejected here while the server accepts it. Unicode letter properties
// keep the two in step: a letter, then letters, combining marks and name punctuation.
const NAME_PATTERN = /^\p{L}[\p{L}\p{M} '.-]*$/u;
const LICENCE_PATTERN = /^[A-Za-z0-9-]+$/;

const NAME_MIN = 3;
const NAME_MAX = 60;

/** Every field either form can show. Unused ones stay as empty strings. */
export const farmerFormShape = z.object({
  crop: z.enum(['cotton', 'hemp']),
  id_number: z.string(),
  name: z.string(),
  phone: z.string(),
  field_office_id: z.string(),
  variety: z.string(),
  tenure: z.string(),
  previous_crop: z.string(),

  // Cotton (Pakistan)
  father_name: z.string(),
  province_code: z.string(),
  district_code: z.string(),
  tehsil_code: z.string(),
  tehsil_name: z.string(),
  village: z.string(),

  // Hemp (United Kingdom)
  farm_name: z.string(),
  home_office_licence_no: z.string(),
  postcode: z.string(),
  county: z.string(),
  region: z.string(),
  /**
   * True only when no source could resolve the postcode. County and region are
   * required, and editable, in exactly that case.
   */
  postcode_manual: z.boolean(),
});

export type FarmerFormValues = z.infer<typeof farmerFormShape>;

type Ctx = z.RefinementCtx;

function required(ctx: Ctx, path: keyof FarmerFormValues, message: string) {
  ctx.addIssue({ code: z.ZodIssueCode.custom, path: [path], message });
}

function checkName(ctx: Ctx, path: keyof FarmerFormValues, value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) return required(ctx, path, `${label} is required.`);
  if (trimmed.length < NAME_MIN || trimmed.length > NAME_MAX) {
    return required(ctx, path, `${label} must be between ${NAME_MIN} and ${NAME_MAX} characters.`);
  }
  if (!NAME_PATTERN.test(trimmed)) {
    required(
      ctx,
      path,
      `${label} may contain letters, spaces, apostrophes, hyphens and dots only.`,
    );
  }
}

export const farmerFormSchema = farmerFormShape.superRefine((values, ctx) => {
  checkName(ctx, 'name', values.name, values.crop === 'cotton' ? 'Name' : 'Farmer name');

  if (!values.field_office_id.trim()) required(ctx, 'field_office_id', 'Choose a field office.');
  if (!values.variety.trim()) required(ctx, 'variety', 'Choose a variety.');
  if (!values.tenure.trim()) required(ctx, 'tenure', 'Choose the land tenure.');

  if (values.crop === 'cotton') {
    if (!values.id_number.trim()) {
      required(ctx, 'id_number', 'CNIC is required.');
    } else if (!isCnic(values.id_number)) {
      required(ctx, 'id_number', 'A CNIC has exactly 13 digits, for example 12345-1234567-1.');
    }

    checkName(ctx, 'father_name', values.father_name, 'Father name');

    if (values.phone.trim() && !isPkMobile(values.phone)) {
      required(ctx, 'phone', 'Enter a Pakistani mobile number, for example 0300-1234567.');
    }

    if (!values.province_code.trim()) required(ctx, 'province_code', 'Choose a province.');
    if (!values.district_code.trim()) required(ctx, 'district_code', 'Choose a district.');

    // A tehsil must be chosen or typed: the rule spans two fields, so it cannot live
    // on either of them alone. Districts with no seeded list rely on the typed one.
    const chosen = values.tehsil_code.trim();
    const typed = values.tehsil_name.trim();
    if (!chosen && !typed) {
      required(ctx, 'tehsil_code', 'Choose a tehsil or city, or type one.');
    } else if (chosen === TEHSIL_OTHER && !typed) {
      required(ctx, 'tehsil_name', 'Type the tehsil or city name.');
    }

    const village = values.village.trim();
    if (!village) required(ctx, 'village', 'Village or town is required.');
    else if (village.length < 2) {
      required(ctx, 'village', 'Village or town must be at least 2 characters.');
    }
    return;
  }

  // Hemp (United Kingdom)
  const digits = normalizeIdNumber(values.id_number).replace(/\D/g, '');
  if (!values.id_number.trim()) {
    required(ctx, 'id_number', 'ID number is required.');
  } else if (
    !/^\d+$/.test(digits) ||
    digits.length < HEMP_ID_MIN_DIGITS ||
    digits.length > HEMP_ID_MAX_DIGITS
  ) {
    required(
      ctx,
      'id_number',
      `The ID number must be between ${HEMP_ID_MIN_DIGITS} and ${HEMP_ID_MAX_DIGITS} digits.`,
    );
  }

  const farm = values.farm_name.trim();
  if (!farm) required(ctx, 'farm_name', 'Farm name is required.');
  else if (farm.length < 2 || farm.length > 80) {
    required(ctx, 'farm_name', 'Farm name must be between 2 and 80 characters.');
  }

  if (values.phone.trim() && !isUkMobile(values.phone)) {
    required(ctx, 'phone', 'Enter a UK mobile number, for example 07700 900123.');
  }

  const licence = values.home_office_licence_no.trim();
  if (!licence) {
    required(ctx, 'home_office_licence_no', 'The Home Office hemp licence number is required.');
  } else if (licence.length < 6 || licence.length > 30) {
    required(
      ctx,
      'home_office_licence_no',
      'The licence number must be between 6 and 30 characters.',
    );
  } else if (!LICENCE_PATTERN.test(licence.replace(/\s/g, ''))) {
    required(
      ctx,
      'home_office_licence_no',
      'The licence number may contain letters, digits and dashes only.',
    );
  }

  if (!values.postcode.trim()) required(ctx, 'postcode', 'Postcode is required.');
  else if (!isUkPostcode(values.postcode)) {
    required(ctx, 'postcode', 'Enter a valid UK postcode, for example CB23 6DP.');
  }

  // Only asked for when nothing could resolve the postcode.
  if (values.postcode_manual) {
    if (!values.county.trim()) required(ctx, 'county', 'Enter the county.');
    if (!values.region.trim()) required(ctx, 'region', 'Enter the region.');
  }
});

/** The value "Other (type manually)" puts in the tehsil select. */
export const TEHSIL_OTHER = '__other__';

export const emptyFarmerForm: FarmerFormValues = {
  crop: 'cotton',
  id_number: '',
  name: '',
  phone: '',
  field_office_id: '',
  variety: '',
  tenure: '',
  previous_crop: '',
  father_name: '',
  province_code: '',
  district_code: '',
  tehsil_code: '',
  tehsil_name: '',
  village: '',
  farm_name: '',
  home_office_licence_no: '',
  postcode: '',
  county: '',
  region: '',
  postcode_manual: false,
};

export function defaultsForCrop(crop: Crop): FarmerFormValues {
  return { ...emptyFarmerForm, crop };
}

/**
 * Fields cleared when the crop changes. The name and phone go too: the phone format
 * differs by country, and keeping a half-valid number would be worse than clearing it.
 */
export const CROP_SPECIFIC_FIELDS: readonly (keyof FarmerFormValues)[] = [
  'id_number',
  'phone',
  'field_office_id',
  'variety',
  'tenure',
  'previous_crop',
  'father_name',
  'province_code',
  'district_code',
  'tehsil_code',
  'tehsil_name',
  'village',
  'farm_name',
  'home_office_licence_no',
  'postcode',
  'county',
  'region',
];
