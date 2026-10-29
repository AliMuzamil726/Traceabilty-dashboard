import type { GateEntry } from '../api/types';

export function entry(over: Partial<GateEntry> = {}): GateEntry {
  return {
    id: 'e1', delivery_id: 'd1', delivery_no: 'DL-0001', site_id: 's1', site_code: 'BWP-G1', site_name: 'Bahawalpur Ginner 1',
    crop: 'cotton', status: 'pending', arrived_at: '2026-10-27T09:00:00Z', vehicle_no: 'MNA-1234', driver_name: 'Akram Ali',
    gross_weight_kg: null, tare_weight_kg: null, net_weight_kg: null, moisture_pct: null,
    accepted_at: null, rejected_at: null, rejection_reason: null, note: null,
    can_accept: true, can_reject: true,
    field_weight_kg: 1000, estimated_quantity_kg: 1200, variance_warn_pct: 3, variance_flag_pct: 5, moisture_warn_pct: 12,
    ...over,
  };
}

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}
