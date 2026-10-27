/** Shapes of /api/v1/dashboard (snake_case, as sent by the API). */

export type Crop = 'cotton' | 'hemp';
export type CropFilter = 'all' | Crop;
export type Bucket = 'no_sowing_data' | 'growing' | 'approaching' | 'ready' | 'harvested';
export type PickupState = 'not_requested' | 'requested' | 'scheduled' | 'delivered';
export type RangeKey = '7d' | '30d' | 'season' | 'custom';
export type Scope = 'mine' | 'all';
export type Severity = 'attention' | 'critical';
export type Interval = 'day' | 'week' | 'month';
export type Metric = 'registrations' | 'deliveries';

/** Where a figure takes you: a route of this app plus the filters to open it with. */
export interface Link {
  path: string;
  params: Record<string, string>;
}

interface SectionBase {
  crop: CropFilter;
  season_year: number;
  scope: Scope;
  generated_at: string;
}

// ------------------------------------------------------------------------ overview

export interface DashboardRange {
  key: RangeKey;
  from: string;
  to: string;
  days: number;
}

export interface Kpis {
  farmers: { total: number; cotton: number; hemp: number };
  fields: { total: number; area: number; area_unit: string; area_by_crop: Record<string, number> };
  fieldbooks: { fields: number; started: number; submitted: number; submitted_pct: number };
  ready_now: { fields: number; estimated_kg: number; awaiting_pickup: number };
  delivered: {
    deliveries: number;
    kg: number;
    maunds: number | null;
    average_moisture_pct: number | null;
  };
  bales: { made: number; weight_kg: number; heaps: number };
  scans: {
    total: number;
    in_range: number;
    public: number;
    internal: number;
    active_codes: number;
    last_scan_at: string | null;
  };
}

export interface Overview extends SectionBase {
  range: DashboardRange;
  officer: { id: string; full_name: string; field_office_name: string | null; is_admin: boolean };
  units: { area: string; mass: string };
  kpis: Kpis;
}

// ------------------------------------------------------------------------ pipeline

export type StageKey =
  | 'farmers'
  | 'fields'
  | 'fieldbooks'
  | 'harvest'
  | 'deliveries'
  | 'bales'
  | 'scans';

export interface Stage {
  key: StageKey;
  title: string;
  caption: string;
  count: number;
  detail: string | null;
  /** Share of the stage before it; null on the first stage. */
  conversion_pct: number | null;
  /** Share of the first stage, for the thin bar. */
  progress_pct: number;
  link: Link;
}

export interface Pipeline extends SectionBase {
  stages: Stage[];
}

// -------------------------------------------------------------------------- charts

export interface SeriesPoint {
  period_start: string;
  value: number | null;
}

export interface Series {
  key: string;
  label: string;
  unit: string;
  total: number | null;
  points: SeriesPoint[];
}

export interface Timeseries extends SectionBase {
  metric: Metric;
  interval: Interval;
  from: string;
  to: string;
  truncated: boolean;
  series: Series[];
}

export interface ReadinessSlice {
  bucket: Bucket;
  label: string;
  fields: number;
  area: number;
  estimated_kg: number;
}

export interface FunnelStep {
  step_key: string;
  title: string;
  order: number;
  complete: number;
  pct: number;
}

export interface HeapUtilisation {
  heap_id: string;
  kind: 'heap' | 'batch';
  crop: Crop;
  status: 'open' | 'closed';
  input_kg: number;
  expected_output_kg: number;
  bales_made: number;
  max_bales: number;
  link: Link;
}

export interface RegionArea {
  region: string;
  fields: number;
  area: number;
}

export interface Distribution extends SectionBase {
  /** Which programme the funnel and the regions describe. */
  focus_crop: Crop;
  area_unit: string;
  region_label: string;
  readiness: ReadinessSlice[];
  fieldbook_funnel: FunnelStep[];
  fieldbooks_started: number;
  heap_utilisation: HeapUtilisation[];
  top_regions: RegionArea[];
}

// -------------------------------------------------------------------------- alerts

export interface AlertSample {
  label: string;
  sublabel: string | null;
  link: Link;
}

export interface Alert {
  key: string;
  title: string;
  description: string;
  count: number;
  severity: Severity;
  link: Link;
  samples: AlertSample[];
}

export interface Alerts extends SectionBase {
  total: number;
  critical: number;
  alerts: Alert[];
}

// ------------------------------------------------------------------------ activity

export interface ActivityItem {
  id: string;
  at: string;
  module: number;
  module_name: string;
  entity: string;
  entity_id: string;
  action: string;
  summary: string;
  officer_id: string | null;
  officer_name: string | null;
  link: Link;
}

export interface Activity {
  module: number | null;
  items: ActivityItem[];
  modules: { number: number; name: string }[];
  generated_at: string;
}

// ----------------------------------------------------------------------------- map

export interface MapFeature {
  type: 'Feature';
  id: string;
  geometry: { type: 'Polygon'; coordinates: number[][][] } | null;
  properties: {
    field_id: string;
    field_code: string;
    farmer_id: string;
    farmer_name: string;
    sawie_id: number;
    crop: Crop;
    status: Bucket;
    status_label: string;
    overdue: boolean;
    pickup_state: PickupState;
    area: number;
    area_unit: string;
    /** [longitude, latitude], as GeoJSON orders them. */
    centroid: [number, number];
  };
}

export interface MapCollection {
  type: 'FeatureCollection';
  features: MapFeature[];
  total: number;
  returned: number;
  truncated: boolean;
  crop: CropFilter;
  season_year: number;
  scope: Scope;
  generated_at: string;
}

// ------------------------------------------------------------------------ officers

export interface OfficerRow {
  officer_id: string;
  code: string;
  full_name: string;
  role: string;
  country: string;
  field_office_name: string | null;
  farmers: number;
  fields: number;
  area: number;
  fieldbooks_submitted: number;
}

export interface OfficerOverview {
  crop: CropFilter;
  season_year: number;
  area_unit: string;
  items: OfficerRow[];
  generated_at: string;
}

// ---------------------------------------------------------------------- onboarding

export interface ChecklistStep {
  key: string;
  title: string;
  description: string;
  done: boolean;
  count: number;
  link: Link;
}

export interface Onboarding {
  is_empty: boolean;
  role: string;
  scope: Scope;
  crop: CropFilter;
  season_year: number;
  counts: { farmers: number; fields: number; fieldbooks: number };
  steps: ChecklistStep[];
  generated_at: string;
}
