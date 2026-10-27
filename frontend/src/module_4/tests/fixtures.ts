import type { FieldsPage, RadarRow } from '../api/types';

export function row(over: Partial<RadarRow> = {}): RadarRow {
  return {
    field_id: 'f1', field_code: '1001-01', farmer_id: 'fa1', sawie_id: 1001, farmer_name: 'Muhammad Imran',
    father_or_farm: 'Ghulam Rasool', location: 'Basti Malook, Multan City, Multan', district: 'Multan',
    tehsil: 'Multan City', village: 'Basti Malook', county: null, region: null, field_office_id: 'o1',
    field_office_name: 'Multan Field Office', officer_id: 'me', officer_name: 'Officer One', area_acre: 9.88,
    area_ha: 4, centroid_lat: 30.1, centroid_lng: 71.5, fieldbook_id: 'b1', sowing_date: '2026-05-01',
    days_after_sowing: 140, progress: 0.7, status: 'ready', status_label: 'Ready', overdue: false,
    expected_ready: '2026-09-13', next_milestone: 'Harvest window closes in 60 days', estimated_kg: 7904,
    estimate_is_benchmark: true, pickup_state: 'not_requested', request_id: null, request_no: null,
    can_act: true, can_request: true, ...over,
  };
}

export function page(items: RadarRow[]): FieldsPage {
  const totals = { fields: 1, area: 9.88, estimated_kg: 7904 };
  return {
    crop: 'cotton', season_year: 2026, area_unit: 'acre',
    buckets: { no_sowing_data: 2, growing: 3, approaching: 1, ready: 4, harvested: 0 },
    kpis: { ready_now: totals, approaching_soon: totals, pickup_requested: totals, overdue: totals, approaching_window_days: 14 },
    clock: { approach_day: 120, ready_day: 135, window_end_day: 200 },
    generated_at: '2026-10-21T10:00:00Z', total_fields: 10, items, total: items.length, page: 1, page_size: 25,
    facets: {
      districts: ['Bahawalpur', 'Multan'], tehsils: { Multan: ['Multan City'] }, villages: { 'Multan City': ['Basti Malook'] },
      counties: [], regions: [], offices: [{ value: 'o1', label: 'Multan Field Office' }], officers: [{ value: 'me', label: 'Officer One' }],
    },
    is_admin: false,
  };
}
