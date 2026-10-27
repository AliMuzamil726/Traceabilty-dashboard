import type { HeapDetail } from '../api/types';

export function heap(over: Partial<HeapDetail> = {}): HeapDetail {
  return {
    id: 'h1', heap_id: 'BWP-G1-H01', crop: 'cotton', status: 'open',
    site: { id: 's1', code: 'BWP-G1', name: 'Bahawalpur Ginner 1', type: 'ginner', address: 'Bahawalpur' },
    opened_at: '2026-10-20T08:00:00Z', opened_by_name: 'Officer One', closed_at: null, closed_by_name: null, close_reason: null,
    outturn_ratio_pct: 34, bale_unit_kg: 170, shiv_pct: null, dust_pct: null, note: null,
    totals: {
      input_kg: '17000.00', input_maunds: '425.00', outturn_ratio_pct: '34', bale_unit_kg: '170.00', expected_output_kg: '5780.00',
      max_bales: 34, bales_made: 0, bales_weight_kg: '0.00', input_per_bale_kg: '500.00', remaining_input_kg: '17000.00',
      remaining_output_kg: '5780.00', consumed_pct: '0.00', can_close: false, can_add_bales: 34, expected_shiv_kg: null, expected_dust_kg: null,
    },
    deliveries: [{ delivery_id: 'd1', delivery_no: 'DL-0001', farmer_id: 'fa1', field_id: 'f1', field_code: '1001-01', sawie_id: 1001,
      farmer_name: 'Muhammad Imran', village_or_farm: 'Basti Malook', delivered_at: '2026-10-20T09:00:00Z', field_weight_kg: null,
      weighbridge_weight_kg: 17000, moisture_pct: 9 }],
    contributions: [{ farmer_id: 'fa1', sawie_id: 1001, farmer_name: 'Muhammad Imran', kg: '17000.00', pct: '100.00', deliveries: 1, fields: 1 }],
    bales: [], pending_deliveries: [],
    permissions: { can_edit_values: true, can_add_deliveries: true, can_remove_deliveries: true, can_record_bales: true,
      can_void_bales: false, can_close: false, can_close_with_remainder: false },
    ...over,
  };
}

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}
