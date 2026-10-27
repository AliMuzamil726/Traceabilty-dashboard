import type { PublicTrace } from '../api/types';

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

export const INVALID = { error: { code: 'qr_invalid', message: 'This code is not valid', details: null } };

export function publicTrace(over: Partial<PublicTrace> = {}): PublicTrace {
  return {
    product: 'Cotton lint bale', crop: 'cotton', bale_serial: 'BWP-G1-H01-001', weight_kg: 170, lot_kind: 'Heap', lot_id: 'BWP-G1-H01',
    season_year: 2026, site: { type: 'Ginner', name: 'Bahawalpur Ginner 1', region: 'Bahawalpur' },
    processing: { opened: '2026-10-01', closed: '2026-10-10' }, programme: 'Pakistan cotton', country: 'Pakistan',
    farms: 3, fields: 3, region_level: 'District', regions: ['Multan'], harvest_window: { from: '2026-09-20', to: '2026-09-28' },
    timeline: [
      { key: 'farmers', label: 'Farmers registered', count: 3, date_from: '2026-04-01', date_to: '2026-04-03', done: true },
      { key: 'bale', label: 'Bale produced', count: 1, date_from: '2026-10-09', date_to: '2026-10-09', done: true },
    ],
    checks: [
      { key: 'fieldbooks_submitted', label: 'All fieldbooks submitted', passed: true, detail: '3 of 3 submitted.' },
      { key: 'deliveries_weighed', label: 'All deliveries weighed', passed: true, detail: '3 of 3 weighed.' },
      { key: 'heap_closed', label: 'Heap closed', passed: true, detail: 'Closed on 10 Oct 2026.' },
      { key: 'mass_balance', label: 'Mass balance', passed: true, detail: 'Bales do not exceed expected output.' },
    ],
    ...over,
  };
}
