import { describe, expect, it } from 'vitest';
import { activeFilterCount, readFilters, toApiParams } from '../hooks/useRadarFilters';
import { monthGrid, shiftMonth } from '../lib/calendar';
import { requestBlockers } from '../lib/selection';
import { row } from './fixtures';

describe('Request pickup selection rules', () => {
  it('allows ready and harvested fields without an open request', () => {
    expect(requestBlockers([row(), row({ field_id: 'f2', status: 'harvested' })])).toEqual([]);
  });

  it('blocks an empty selection', () => {
    expect(requestBlockers([])).toEqual(['Select at least one field.']);
  });

  it('lists every reason, naming the fields', () => {
    const reasons = requestBlockers([
      row(),
      row({ field_id: 'f2', field_code: '1002-01', status: 'growing' }),
      row({ field_id: 'f3', field_code: '1003-01', status: 'no_sowing_data' }),
      row({ field_id: 'f4', field_code: '1004-01', pickup_state: 'requested' }),
      row({ field_id: 'f5', field_code: '1005-01', pickup_state: 'scheduled' }),
      row({ field_id: 'f6', field_code: '1006-01', can_act: false }),
    ]);
    expect(reasons).toEqual([
      'Not ready or harvested: 1002-01, 1003-01',
      'Pickup already requested: 1004-01, 1005-01',
      "Another officer's farmer: 1006-01",
    ]);
  });

  it('shortens long lists', () => {
    const many = Array.from({ length: 5 }, (_, i) => row({ field_id: `g${i}`, field_code: `20${i}-01`, status: 'approaching' }));
    expect(requestBlockers(many)[0]).toBe('Not ready or harvested: 200-01, 201-01, 202-01 and 2 more');
  });
});

describe('URL filters', () => {
  it('reads defaults and ignores nonsense', () => {
    const f = readFilters(new URLSearchParams('crop=wheat&view=nope&page=-2&season=12'));
    expect(f.crop).toBe('cotton');
    expect(f.view).toBe('table');
    expect(f.page).toBe(1);
    expect(f.season).toBe(new Date().getFullYear());
    expect(f.scope).toBe('mine');
  });

  it('sends only the location filters of the chosen crop', () => {
    const cotton = toApiParams(readFilters(new URLSearchParams('district=Multan&county=Lincolnshire&status=ready&from=2026-10-01')));
    expect(cotton).toMatchObject({ crop: 'cotton', district: 'Multan', county: undefined, status: 'ready', ready_from: '2026-10-01' });
    const hemp = toApiParams(readFilters(new URLSearchParams('crop=hemp&district=Multan&county=Lincolnshire')));
    expect(hemp).toMatchObject({ crop: 'hemp', district: undefined, county: 'Lincolnshire' });
  });

  it('counts the active filters', () => {
    expect(activeFilterCount(readFilters(new URLSearchParams('q=imran&status=ready&view=map&sort=-das')))).toBe(2);
  });
});

describe('calendar arithmetic', () => {
  it('pads the month to start on Monday', () => {
    const october = monthGrid('2026-10'); // 1 October 2026 is a Thursday
    expect(october.slice(0, 4)).toEqual([null, null, null, '2026-10-01']);
    expect(october.filter(Boolean)).toHaveLength(31);
  });

  it('moves across years', () => {
    expect(shiftMonth('2026-12', 1)).toBe('2027-01');
    expect(shiftMonth('2026-01', -1)).toBe('2025-12');
  });
});
