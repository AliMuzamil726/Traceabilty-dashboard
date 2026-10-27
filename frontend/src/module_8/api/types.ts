/** Shapes returned by /api/v1/settings. Mirrors backend/module_8/schemas.py. */

export type SettingType = 'string' | 'int' | 'float' | 'bool' | 'choice' | 'json';
export type SettingSource = 'database' | 'env' | 'default';

export interface Setting {
  key: string;
  group: string;
  label: string;
  description: string;
  type: SettingType;
  value: unknown;
  default: unknown;
  source: SettingSource;
  version: number;
  minimum: number | null;
  maximum: number | null;
  pattern: string | null;
  choices: unknown[] | null;
  sensitive: boolean;
  needs_restart: boolean;
  read_by: string[];
  public: boolean;
  is_default: boolean;
  changed_by: string | null;
  changed_at: string | null;
}

export interface SettingsPage {
  items: Setting[];
  groups: string[];
}

export interface HistoryEntry {
  id: string;
  key: string;
  old_value: unknown;
  new_value: unknown;
  changed_by: string | null;
  changed_by_name?: string | null;
  changed_at: string;
  reason: string | null;
}

export interface Officer {
  id: string;
  code: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  role: 'officer' | 'staff' | 'admin';
  country: string;
  field_office_id: string | null;
  field_office_name: string | null;
  is_dummy: boolean;
  active: boolean;
  usage: number;
  last_activity: string | null;
  can_deactivate: boolean;
}

export interface Office {
  id: string;
  code: string;
  name: string;
  country: string;
  province: string | null;
  district: string | null;
  is_dummy: boolean;
  active: boolean;
  officer_count: number;
  usage: number;
}

export interface UsageItem {
  label: string;
  count: number;
}

export interface Site {
  id: string;
  code: string;
  name: string;
  type: 'ginner' | 'processor';
  crop: 'cotton' | 'hemp';
  country: string;
  address: string | null;
  region: string | null;
  contact_person: string | null;
  contact_phone: string | null;
  is_dummy: boolean;
  active: boolean;
  usage: number;
  usage_breakdown: UsageItem[];
  code_locked: boolean;
}

export interface ListSummary {
  key: string;
  label: string;
  group: string;
  values: number;
  active_values: number;
  required_by: string[];
}

export interface ListValue {
  id: string;
  list_key: string;
  value: string;
  label: string;
  sort_order: number;
  active: boolean;
  crop: string | null;
  country: string | null;
  usage: number;
  can_delete: boolean;
}

export interface ImportReport {
  created: number;
  updated: number;
  skipped: number;
  errors: { row?: number; message?: string; [key: string]: unknown }[];
  ok: boolean;
  preview?: Record<string, unknown>[];
  dry_run?: boolean;
}

export interface LocationNode {
  id: string;
  code: string | null;
  name: string;
  level: string;
  country: string;
  active: boolean;
  usage: number;
  children: LocationNode[];
}

export interface LocationTree {
  country: string;
  labels: Record<string, string>;
  levels: string[];
  items: LocationNode[];
}

export interface RenamePreview {
  id: string;
  from: string;
  to: string;
  farmers_affected: number;
}

export interface MergePreview {
  from: string;
  to: string;
  farmers_affected: number;
  children_moved: number;
}

/** Crop clock, delivery tolerances and heap defaults share this shape. */
export interface CropConfig {
  key: string;
  version: number;
  crops: Record<string, Record<string, number>>;
}

export interface AlertConfig {
  key: string;
  version: number;
  values: Record<string, number>;
  defaults: Record<string, number>;
}

export interface ClockPreview {
  fields_examined: number;
  fields_moving: number;
  before: Record<string, number>;
  after: Record<string, number>;
  moves: { from: string; to: string; fields: number }[];
}

export interface PermissionRow {
  key: string;
  module: number | null;
  label: string;
  description: string;
  officer: boolean;
  staff: boolean;
  admin: boolean;
}

export interface AuditEntry {
  id: string;
  entity: string;
  entity_id: string;
  module: number | null;
  action: string;
  officer_id: string | null;
  officer_name: string | null;
  diff: Record<string, unknown>;
  request_id: string | null;
  created_at: string;
}

export interface AuditPage {
  items: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditFacets {
  entities: string[];
  actions: string[];
  officers: { id: string; name: string }[];
  modules: number[];
}

export interface Backup {
  id: string;
  filename: string;
  size_bytes: number;
  created_by: string | null;
  created_at: string;
  note: string | null;
  kind: 'manual' | 'safety';
  present: boolean;
}

export interface BackupStatus {
  supported: boolean;
  dialect: string;
  reason: string | null;
  instructions: string | null;
  directory: string | null;
  database_bytes: number | null;
  maintenance: boolean;
}

export interface RestoreResult {
  filename: string;
  safety_backup: string;
  integrity: string;
  counts_before: Record<string, number>;
  counts_after: Record<string, number>;
}

export interface HealthCheck {
  key: string;
  label: string;
  status: 'ok' | 'warn' | 'fail';
  detail: string;
}

export interface SystemInfo {
  app: Record<string, unknown>;
  runtime: Record<string, unknown>;
  database: Record<string, unknown>;
  counts: { table: string; rows: number }[];
  health: HealthCheck[];
  seed: Record<string, unknown>;
}

export interface DummyRow {
  id: string;
  code: string;
  name: string;
  usage: number;
}

export interface DummyData {
  officers: DummyRow[];
  offices: DummyRow[];
  sites: DummyRow[];
  removable: number;
}

export interface DummyRemoved {
  removed: { officers: string[]; offices: string[]; sites: string[] };
  removed_total: number;
  kept: { kind: string; code: string; usage: number }[];
}

export interface TileLayer {
  key: string;
  label: string;
  url: string;
  attribution: string;
  max_zoom: number;
  tile_size?: number;
  zoom_offset?: number;
  fallback_reason?: string;
}

export interface PublicConfig {
  settings: Record<string, unknown>;
  map: {
    tiles: TileLayer;
    labels_overlay: boolean;
    labels_overlay_url: string;
    centres: Record<string, { lat: number; lng: number; zoom: number }>;
    geolocation_prompt: boolean;
  };
  qr: { public_base_url: string; label_caption: string };
  programme: { current_season: number | null; season_label: string };
  cache_seconds: number;
}

export interface TestResult {
  ok: boolean;
  status: number | null;
  detail: string;
  warning: string | null;
  url: string | null;
}

export interface Preferences {
  sidebar_collapsed: boolean;
  table_density: 'comfortable' | 'compact';
  default_crop: 'all' | 'cotton' | 'hemp';
}
