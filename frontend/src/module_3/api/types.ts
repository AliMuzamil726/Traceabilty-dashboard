/** Shapes of /api/v1/fieldbook (snake_case, as sent by the API). */

export type Crop = 'cotton' | 'hemp';

// ------------------------------------------------------------------ form definitions

export type FieldType =
  | 'text'
  | 'number'
  | 'date'
  | 'dates'
  | 'select'
  | 'multiselect'
  | 'yesno'
  | 'paired_number'
  | 'photos';

export interface VisibleIf {
  field: string;
  in?: string[];
  not_in?: string[];
}

export interface FieldPart {
  key: string;
  label: string;
  unit?: string;
  min?: number;
  max?: number;
}

export type Computed =
  | { kind: 'count'; of: string }
  | { kind: 'days_between'; from: string; to: string }
  | { kind: 'product'; of: string[] };

export interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  unit?: string;
  min?: number;
  max?: number;
  integer?: boolean;
  required?: boolean;
  list_key?: string;
  default_from?: string;
  readonly?: boolean;
  visible_if?: VisibleIf;
  help?: string;
  not_future?: boolean;
  warn_above?: number;
  warn_values?: string[];
  warn_message?: string;
  computed?: Computed;
  parts?: FieldPart[];
  suggest_from?: { field: string; part?: string };
}

export interface StepTotal {
  label: string;
  kind: 'count' | 'sum' | 'sum_product' | 'sum_part';
  field?: string;
  fields?: string[];
  part?: string;
  factor?: number;
  unit?: string;
}

export interface StepDef {
  key: string;
  title: string;
  order: number;
  repeatable: boolean;
  required: boolean;
  allow_not_applicable?: boolean;
  summary?: string;
  totals?: StepTotal[];
  fields: FieldDef[];
  rules?: Record<string, unknown>[];
  suggestions?: Record<string, Record<string, Record<string, number>>>;
}

export interface FormDefinition {
  crop: Crop;
  country: string;
  version: string;
  title?: string;
  area_unit: string;
  area_ref: string;
  sowing_date_ref: string;
  harvest_step: string;
  pickup: { step: string; field: string; label_field: string | null };
  steps: StepDef[];
}

// ------------------------------------------------------------------ fieldbooks

export type EntryData = Record<string, unknown>;
export type StepStatus = 'not_started' | 'in_progress' | 'complete' | 'not_applicable';

export interface Issue {
  step_key: string;
  entry_index: number;
  field: string;
  level: 'error' | 'warning';
  message: string;
}

export interface Entry {
  entry_index: number;
  data: EntryData;
  completed: boolean;
  updated_at: string;
  updated_by: string | null;
}

export interface StepState {
  key: string;
  status: StepStatus | string;
  entry_count: number;
  entries: Entry[];
}

export interface Photo {
  id: string;
  original_name: string;
  mime: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  uploaded_at: string;
  url: string;
  thumb_url: string;
}

export interface CropClock {
  crop: string;
  approach_day: number;
  ready_day: number;
  window_end_day: number;
}

export interface CropStatus {
  status: 'no_sowing_data' | 'growing' | 'approaching' | 'ready' | 'harvested' | string;
  label: string;
  days_after_sowing: number | null;
  sowing_date: string | null;
  overdue: boolean;
  next_milestone: string;
}

export interface FarmerCard {
  id: string;
  sawie_id: number;
  name: string;
  crop: Crop | string;
  country: string;
  registered_by: string | null;
  home_office_licence_no: string | null;
}

export interface FieldCard {
  id: string;
  field_id: string;
  area_acre: number;
  area_ha: number;
}

export interface Book {
  id: string;
  field_id: string;
  field_code: string;
  farmer_id: string;
  crop: Crop;
  season_year: number;
  status: 'draft' | 'submitted';
  locked: boolean;
  current_step: string | null;
  schema_version: string;
  version: number;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  submitted_at: string | null;
  submitted_by: string | null;
  ready_for_pickup_at: string | null;
  farmer: FarmerCard;
  field: FieldCard;
  defaults: Record<string, unknown>;
  steps: StepState[];
  photos: Photo[];
  warnings: Issue[];
  errors: Issue[];
  missing_steps: string[];
  crop_clock: CropClock;
  crop_status: CropStatus;
}

export interface SaveResult {
  book: Book;
  warnings: Issue[];
}

export interface TimelineItem {
  at: string;
  step_key: string | null;
  step_title: string | null;
  entry_index: number | null;
  kind: 'entry' | 'not_applicable' | 'created' | 'submitted';
  summary: string;
  officer_id: string | null;
  officer_name: string | null;
}

// ------------------------------------------------------------------ selectors

export interface OfficerOption {
  id: string;
  code: string;
  full_name: string;
  role: string;
  country: string;
  field_office_name: string | null;
}

export type FarmerBookStatus = 'no_field' | 'not_started' | 'in_progress' | 'submitted';

export interface FarmerOption {
  id: string;
  sawie_id: number;
  name: string;
  crop: Crop | string;
  field_count: number;
  drafts: number;
  submitted: number;
  fieldbook_status: FarmerBookStatus | string;
}

export interface FieldOption {
  id: string;
  field_id: string;
  area_acre: number;
  area_ha: number;
  fieldbook_id: string | null;
  fieldbook_status: 'none' | 'draft' | 'submitted' | string;
}

export interface FieldSelector {
  farmer: FarmerCard;
  season_year: number;
  items: FieldOption[];
}
