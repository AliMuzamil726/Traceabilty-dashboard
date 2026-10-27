import type { DeliveryDetail } from '../api/types';

export function delivery(over: Partial<DeliveryDetail> = {}): DeliveryDetail {
  return {
    id: 'd1', delivery_no: 'DL-0001', pickup_request_id: 'r1', farmer_id: 'fa1', field_id: 'f1', field_code: '1001-01',
    sawie_id: 1001, farmer_name: 'Muhammad Imran', father_or_farm: 'Ghulam Rasool', location: 'Basti Malook, Multan City, Multan',
    district: 'Multan', county: null, officer_name: 'Officer One', crop: 'cotton', season_year: 2026, status: 'in_transit',
    site: { id: 's1', code: 'BWP-G1', name: 'Bahawalpur Ginner 1 (dummy)', type: 'ginner', country: 'PK' }, heap_id: null,
    scheduled_date: '2026-10-23', driver_name: 'Akram Ali', driver_phone: '+923017654321', vehicle_no: 'MNA-1234',
    dispatched_at: '2026-10-22T08:00:00Z', delivered_at: null, estimated_quantity_kg: 1000, field_weight_kg: null,
    weighbridge_weight_kg: null, weighbridge_maunds: null, moisture_pct: null, variance_kg: null, variance_pct: null,
    variance_level: null, note: null, cancel_reason: null, created_at: '2026-10-22T07:00:00Z', updated_at: '2026-10-22T08:00:00Z',
    can_act: true, history: [{ from_status: null, to_status: 'scheduled', officer_id: 'o', officer_name: 'Officer One', at: '2026-10-22T07:00:00Z', note: null }],
    thresholds: { variance_warn_pct: 3, variance_flag_pct: 5, moisture_warn_pct: 12 },
    ...over,
  };
}

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}
