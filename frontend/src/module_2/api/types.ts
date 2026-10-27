/**
 * Shapes returned by the Module 2 API (snake_case, exactly as the backend sends them).
 * Mirrors backend/module_2/schemas.py; see docs/CONTRACTS.md.
 */

export type Crop = 'cotton' | 'hemp';

/** GeoJSON Polygon in WGS84, as [longitude, latitude] pairs. */
export interface PolygonGeometry {
  type: 'Polygon';
  coordinates: number[][][];
}

export interface FieldOfficeRef {
  id: string;
  code: string;
  name: string;
}

export interface OfficerRef {
  id: string | null;
  code: string | null;
  full_name: string | null;
}

export interface SeasonProfile {
  season_year: number;
  variety: string;
  tenure: string;
  previous_crop: string | null;
  notes: string | null;
  updated_at: string;
}

export interface FarmerListItem {
  id: string;
  sawie_id: number;
  crop: Crop;
  country: string;
  name: string;
  father_name: string | null;
  farm_name: string | null;
  id_number_masked: string;
  phone_masked: string | null;
  location_summary: string;
  field_office: FieldOfficeRef | null;
  registered_by: OfficerRef | null;
  field_count: number;
  has_fields: boolean;
  created_at: string;
}

export interface Farmer {
  id: string;
  sawie_id: number;
  crop: Crop;
  country: string;
  name: string;
  father_name: string | null;
  farm_name: string | null;
  /** Masked unless this officer registered the farmer, or is an administrator. */
  id_number: string;
  phone: string | null;
  sensitive_visible: boolean;
  province: string | null;
  district: string | null;
  tehsil: string | null;
  village: string | null;
  home_office_licence_no: string | null;
  postcode: string | null;
  county: string | null;
  region: string | null;
  field_office: FieldOfficeRef | null;
  registered_by: OfficerRef | null;
  created_at: string;
  updated_at: string;
}

/** Personal data only. Crop data is never pre-filled from a lookup. */
export interface FarmerPersonal {
  name: string;
  father_name: string | null;
  farm_name: string | null;
  phone: string | null;
  province_code: string | null;
  province: string | null;
  district_code: string | null;
  district: string | null;
  tehsil_code: string | null;
  tehsil: string | null;
  village: string | null;
  home_office_licence_no: string | null;
  postcode: string | null;
  county: string | null;
  region: string | null;
  field_office_id: string | null;
}

export interface FarmerLookup {
  exists: boolean;
  crop: Crop;
  id_number_masked: string | null;
  next_sawie_id_preview: number | null;
  sawie_id: number | null;
  farmer_id: string | null;
  crop_mismatch: boolean;
  registered_crop: Crop | null;
  registered_country: string | null;
  registered_by: OfficerRef | null;
  registered_at: string | null;
  field_office: FieldOfficeRef | null;
  registered_by_other_officer: boolean;
  personal: FarmerPersonal | null;
  field_count: number;
}

export interface Field {
  id: string;
  field_id: string;
  farmer_id: string;
  geometry: PolygonGeometry;
  area_m2: number;
  area_acre: number;
  area_ha: number;
  vertex_count: number;
  centroid_lat: number;
  centroid_lng: number;
  pin_lat: number;
  pin_lng: number;
  /** [min_lng, min_lat, max_lng, max_lat] */
  bbox: number[];
  created_at: string;
  updated_at: string;
}

export interface FarmerFields {
  items: Field[];
  total: number;
  next_field_id_preview: string;
}

export interface FarmerCompleteness {
  has_fields: boolean;
  field_count: number;
  total_area_acre: number;
  total_area_ha: number;
  ready_for_fieldbook: boolean;
  missing: string[];
}

export interface FarmerProfile {
  farmer: Farmer;
  season_profiles: SeasonProfile[];
  fields: Field[];
  completeness: FarmerCompleteness;
}

export interface FarmerSaved {
  farmer: Farmer;
  created: boolean;
  season_profile: SeasonProfile;
  next_field_id_preview: string;
}

export interface OverlapConflict {
  field_id: string;
  field_code: string;
  farmer_id: string;
  farmer_name: string;
  sawie_id: number;
  overlap_m2: number;
  overlap_percent_of_new_field: number;
}

export interface GeometryValidation {
  valid: boolean;
  area_m2: number | null;
  area_acre: number | null;
  area_ha: number | null;
  vertex_count: number | null;
  centroid_lat: number | null;
  centroid_lng: number | null;
  pin_lat: number | null;
  pin_lng: number | null;
  error_code: string | null;
  message: string | null;
  conflicts: OverlapConflict[];
}

export interface MapFeature {
  id: string;
  field_id: string;
  farmer_id: string;
  farmer_name: string;
  sawie_id: number;
  crop: Crop;
  area_acre: number;
  area_ha: number;
  pin_lat: number;
  pin_lng: number;
  /** Null below the geometry zoom threshold, where the layer is clustered points. */
  geometry: PolygonGeometry | null;
}

export interface MapFields {
  items: MapFeature[];
  total: number;
  returned: number;
  truncated: boolean;
  mode: 'outlines' | 'points';
  limit: number;
}

export interface LocationOption {
  value: string;
  label: string;
  level: string;
  parent_code: string | null;
}

export interface LocationList {
  items: LocationOption[];
  /** True when the form should offer "Other (type manually)". */
  allow_manual: boolean;
}

export interface PostcodeLocation {
  postcode: string;
  county: string | null;
  region: string | null;
  source: string;
  resolved: boolean;
  /** Only true when nothing resolved the postcode, which is when manual entry opens. */
  editable: boolean;
}

/** Request body for creating or updating a farmer. */
export interface FarmerInput {
  crop: Crop;
  id_number: string;
  name: string;
  field_office_id: string;
  father_name?: string | null;
  province_code?: string | null;
  district_code?: string | null;
  tehsil_code?: string | null;
  tehsil_name?: string | null;
  village?: string | null;
  farm_name?: string | null;
  home_office_licence_no?: string | null;
  postcode?: string | null;
  county?: string | null;
  region?: string | null;
  phone?: string | null;
  variety: string;
  tenure: string;
  previous_crop?: string | null;
  season_year?: number | null;
  notes?: string | null;
}
