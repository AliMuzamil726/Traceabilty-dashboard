/**
 * Test fixtures read straight from the backend: the real form definitions and the real
 * master-list seed, so these tests break if the schemas and the screen drift apart.
 */
import { vi } from 'vitest';
import cottonJson from '../../../../backend/module_3/form_definitions/cotton.json';
import hempJson from '../../../../backend/module_3/form_definitions/hemp.json';
import masterRows from '../../../../backend/scripts/seed_data/master_lists.json';
import type { FormDefinition, StepDef } from '../api/types';

export const cotton = cottonJson as unknown as FormDefinition;
export const hemp = hempJson as unknown as FormDefinition;

interface Row {
  list_key: string;
  value: string;
  label: string;
  sort_order: number;
  country: string | null;
  crop: string | null;
}

export function step(def: FormDefinition, key: string): StepDef {
  const found = def.steps.find((s) => s.key === key);
  if (!found) throw new Error(`No step ${key}`);
  return found;
}

/** Answers /api/v1/master/{key} from the seed file, scoped like the backend. */
export function mockMasterLists() {
  const rows = masterRows as Row[];
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://test');
    const match = url.pathname.match(/\/v1\/master\/([^/]+)$/);
    if (!match) return new Response(JSON.stringify({ error: { code: 'not_found', message: 'nope', details: null } }), { status: 404 });
    const key = match[1]!;
    const country = url.searchParams.get('country');
    const crop = url.searchParams.get('crop');
    const items = rows
      .filter((r) => r.list_key === key)
      .filter((r) => !r.country || !country || r.country === country)
      .filter((r) => !r.crop || !crop || r.crop === crop)
      .sort((a, b) => a.sort_order - b.sort_order);
    return new Response(JSON.stringify({ list_key: key, country, crop, items }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
}
