/** Shapes of /api/v1/radar (snake_case, as sent by the API). */

export type Crop = 'cotton' | 'hemp';
export type Bucket = 'no_sowing_data' | 'growing' | 'approaching' | 'ready' | 'harvested';
export type PickupState = 'not_requested' | 'requested' | 'scheduled' | 'delivered';
export type RequestStatus = 'requested' | 'scheduled' | 'fulfilled' | 'cancelled';

export interface RadarRow {
  field_id: string;
  field_code: string;
  farmer_id: string;
  sawie_id: number;
  farmer_name: string;
  father_or_farm: string | null;
  location: string;
  district: string | null;
  tehsil: string | null;
  village: string | null;
  county: string | null;
  region: string | null;
  field_office_id: string;
  field_office_name: string | null;
  officer_id: string | null;
  officer_name: string | null;
  area_acre: number;
  area_ha: number;
  centroid_lat: number;
  centroid_lng: number;
  fieldbook_id: string | null;
  sowing_date: string | null;
  days_after_sowing: number | null;
  progress: number | null;
  status: Bucket;
  status_label: string;
  overdue: boolean;
  expected_ready: string | null;
  next_milestone: string;
  estimated_kg: number | null;
  estimate_is_benchmark: boolean;
  pickup_state: PickupState;
  request_id: string | null;
  request_no: string | null;
  can_act: boolean;
  can_request: boolean;
}

export interface Totals {
  fields: number;
  area: number;
  estimated_kg: number;
}

export interface Kpis {
  ready_now: Totals;
  approaching_soon: Totals;
  pickup_requested: Totals;
  overdue: Totals;
  approaching_window_days: number;
}

export interface Option {
  value: string;
  label: string;
}

export interface Facets {
  districts: string[];
  tehsils: Record<string, string[]>;
  villages: Record<string, string[]>;
  counties: string[];
  regions: string[];
  offices: Option[];
  officers: Option[];
}

export interface Summary {
  crop: Crop;
  season_year: number;
  area_unit: 'acre' | 'ha';
  buckets: Record<Bucket, number>;
  kpis: Kpis;
  clock: { approach_day: number; ready_day: number; window_end_day: number };
  generated_at: string;
  total_fields: number;
}

export interface FieldsPage extends Summary {
  items: RadarRow[];
  total: number;
  page: number;
  page_size: number;
  facets: Facets;
  is_admin: boolean;
}

export interface MapFeature {
  type: 'Feature';
  id: string;
  geometry: { type: 'Polygon'; coordinates: number[][][] } | null;
  properties: {
    field_id: string;
    field_code: string;
    farmer_name: string;
    sawie_id: number;
    status: Bucket;
    status_label: string;
    overdue: boolean;
    next_milestone: string;
    pickup_state: PickupState;
    centroid: [number, number];
    can_request: boolean;
  };
}

export interface MapCollection {
  type: 'FeatureCollection';
  features: MapFeature[];
  total: number;
  truncated: boolean;
}

export interface CalendarData {
  month: string;
  days: { date: string; fields: number; estimated_kg: number }[];
  weeks: { week_start: string; fields: number; estimated_kg: number }[];
}

export interface PickupRequest {
  id: string;
  request_no: string;
  field_id: string;
  field_code: string;
  farmer_id: string;
  farmer_name: string | null;
  sawie_id: number | null;
  crop: Crop;
  season_year: number;
  status: RequestStatus;
  estimated_quantity_kg: number | null;
  quantity_is_estimate: boolean;
  preferred_date: string | null;
  note: string | null;
  requested_by: string | null;
  requested_by_name: string | null;
  requested_at: string;
  cancelled_by: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  delivery_id: string | null;
  updated_at: string;
  can_cancel: boolean;
}

export interface Skipped {
  field_id: string;
  field_code: string | null;
  code: string;
  reason: string;
}

export interface PickupResult {
  created: PickupRequest[];
  skipped: Skipped[];
}
