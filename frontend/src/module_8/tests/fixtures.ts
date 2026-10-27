/** Fixtures for the Module 8 tests. Shapes mirror backend/module_8/schemas.py. */

import type { ListSummary, ListValue, Preferences, Setting, SettingsPage } from '../api/types';

export function officer(isAdmin: boolean) {
  return {
    id: isAdmin ? 'a1' : 'o1',
    code: isAdmin ? 'ADMIN-01' : 'PK-MUL-01',
    full_name: isAdmin ? 'Hassan Qureshi' : 'Ayesha Khan',
    role: isAdmin ? 'admin' : 'officer',
    country: 'PK',
    field_office_id: null,
    field_office_name: null,
    is_admin: isAdmin,
  };
}

export function setting(over: Partial<Setting> = {}): Setting {
  return {
    key: 'validation.hemp_id_min_digits',
    group: 'validation',
    label: 'Hemp ID number: fewest digits',
    description: "A UK grower's identity number must have at least this many digits.",
    type: 'int',
    value: 9,
    default: 9,
    source: 'default',
    version: 3,
    minimum: 1,
    maximum: 20,
    pattern: null,
    choices: null,
    sensitive: false,
    needs_restart: false,
    read_by: ['Register Farmer'],
    public: false,
    is_default: true,
    changed_by: null,
    changed_at: null,
    ...over,
  };
}

export function registry(): SettingsPage {
  return {
    items: [setting()],
    groups: ['programme', 'validation', 'radar', 'alerts', 'map', 'qr'],
  };
}

export function preferences(): Preferences {
  return { sidebar_collapsed: false, table_density: 'comfortable', default_crop: 'all' };
}

export const lists: ListSummary[] = [
  {
    key: 'fertiliser',
    label: 'Fertiliser',
    group: 'shared',
    values: 2,
    active_values: 2,
    required_by: ['Fieldbook: Soil and nutrition'],
  },
];

export function listValues(): ListValue[] {
  return [
    {
      id: 'v1',
      list_key: 'fertiliser',
      value: 'urea',
      label: 'Urea',
      sort_order: 1,
      active: true,
      crop: null,
      country: null,
      usage: 12,
      can_delete: false,
    },
    {
      id: 'v2',
      list_key: 'fertiliser',
      value: 'potash',
      label: 'Potash',
      sort_order: 2,
      active: true,
      crop: null,
      country: null,
      usage: 0,
      can_delete: true,
    },
  ];
}
