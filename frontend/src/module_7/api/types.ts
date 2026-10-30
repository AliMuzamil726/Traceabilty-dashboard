/** Shapes of /api/v1/qr (snake_case, as sent by the API). */

export type Crop = 'cotton' | 'hemp';
export type TokenStatus = 'active' | 'revoked';

export interface LotItem {
  heap_id: string;
  crop: Crop;
  status: 'open' | 'closed';
  site_id: string;
  opened_at: string;
  closed_at: string | null;
  token: string | null;
}

export interface LotsResponse {
  items: LotItem[];
  base_url: string;
  base_url_is_local: boolean;
}

export interface LotFarmer {
  farmer_id: string;
  sawie_id: number | null;
  farmer_name: string | null;
  kg: number;
  pct: number;
}

export interface LotOverview {
  heap_id: string;
  crop: Crop;
  kind: 'Heap' | 'Batch';
  status: 'open' | 'closed';
  site_name: string | null;
  site_address: string | null;
  opened_at: string;
  closed_at: string | null;
  input_kg: number;
  outturn_ratio_pct: number;
  expected_output_kg: number;
  bales_made: number;
  max_bales: number;
  token: string | null;
  trace_url: string | null;
  scans_total: number;
  scans_public: number;
  last_scan_at: string | null;
  farmers: LotFarmer[];
  base_url: string;
  base_url_is_local: boolean;
}

export interface BaleRow {
  bale_serial: string;
  weight_kg: number;
  bale_status: 'active' | 'voided';
  created_at: string;
  token: string | null;
  token_status: TokenStatus | null;
  trace_url: string | null;
  label_print_count: number;
  last_printed_at: string | null;
  scan_count: number;
}

export interface Check {
  key: 'fieldbooks_submitted' | 'deliveries_weighed' | 'heap_closed' | 'mass_balance' | string;
  label: string;
  passed: boolean;
  detail: string;
}

export interface TimelineStep {
  key: string;
  label: string;
  count: number | null;
  date_from: string | null;
  date_to: string | null;
  done: boolean;
}

/** What anyone sees by scanning. No names, numbers, villages or coordinates. */
export interface PublicTrace {
  product: string;
  crop: Crop;
  bale_serial: string | null;
  weight_kg: number | null;
  lot_kind: 'Heap' | 'Batch';
  lot_id: string;
  season_year: number | null;
  site: { type: 'Ginner' | 'Processor'; name: string | null; region: string | null };
  processing: { opened: string | null; closed: string | null };
  programme: string;
  country: string;
  farms: number;
  fields: number;
  region_level: 'District' | 'County';
  regions: string[];
  harvest_window: { from: string | null; to: string | null };
  timeline: TimelineStep[];
  checks: Check[];
}

export interface TraceFarmer {
  farmer_id: string;
  sawie_id: number | null;
  name: string;
  father_or_farm: string | null;
  id_number: string | null;
  phone: string | null;
  sensitive_visible: boolean;
  licence_no: string | null;
  location: string | null;
  registered_by: string | null;
  registered_at: string | null;
  kg: number | null;
  pct: number | null;
}

export interface FieldbookLogEntry {
  at: string;
  step: string;
  kind: string;
  summary: string;
  officer: string | null;
}

export interface GeoPolygon {
  type: 'Polygon' | 'MultiPolygon';
  coordinates: unknown;
}

export interface TraceField {
  field_id: string;
  field_code: string;
  farmer_id: string;
  area_acre: number | null;
  area_ha: number | null;
  geometry: GeoPolygon | null;
  centre: [number, number] | null;
  season_year: number;
  fieldbook: { id: string; status: string; submitted_at: string | null; steps_complete: number; steps_total: number } | null;
  log: FieldbookLogEntry[];
}

export interface TraceDelivery {
  id: string;
  delivery_no: string;
  farmer_id: string;
  field_id: string;
  field_code: string;
  status: string;
  delivered_at: string | null;
  field_weight_kg: number | null;
  weighbridge_weight_kg: number | null;
  moisture_pct: number | null;
  vehicle_no: string | null;
}

export interface InternalTrace {
  token: string | null;
  bale: { serial: string; weight_kg: number; status: string; created_at: string } | null;
  heap: {
    heap_id: string;
    crop: Crop;
    status: 'open' | 'closed';
    kind: 'Heap' | 'Batch';
    site_name: string | null;
    site_code: string | null;
    opened_at: string;
    closed_at: string | null;
    input_kg: number;
    expected_output_kg: number;
    outturn_ratio_pct: number;
    bales_made: number;
    max_bales: number;
  };
  deliveries: TraceDelivery[];
  farmers: TraceFarmer[];
  fields: TraceField[];
  checks: Check[];
}

export interface Resolved {
  kind: 'bale' | 'heap';
  heap_id: string;
  bale_serial: string | null;
  token: string | null;
  token_status: TokenStatus | null;
}

export interface ScanSummary {
  total: number;
  public: number;
  internal: number;
  last_scan_at: string | null;
  active_tokens: number;
  generated_at: string;
}
