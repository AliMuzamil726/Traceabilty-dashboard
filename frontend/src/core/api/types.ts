/** Shapes of the shared backend endpoints (snake_case, as sent by the API). */

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type Role = 'officer' | 'staff' | 'admin';

export interface FieldOfficeRef {
  id: string;
  code: string;
  name: string;
}

export interface Officer {
  id: string;
  code: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  role: Role;
  country: string;
  field_office_id: string | null;
  field_office: FieldOfficeRef | null;
  is_dummy: boolean;
  active: boolean;
}

/** What the sign-in picker sees: no email or phone. */
export interface OfficerDirectoryEntry {
  id: string;
  full_name: string;
  role: Role;
  country: string;
  field_office: FieldOfficeRef | null;
  active: boolean;
}

export interface CurrentOfficer {
  id: string;
  code: string;
  full_name: string;
  role: Role;
  country: string;
  field_office_id: string | null;
  field_office_name: string | null;
  email: string | null;
  phone: string | null;
  /** True once a profile photo has been uploaded (administrators and staff only). */
  has_photo: boolean;
  is_admin: boolean;
  /** Administrator or staff: works on every officer's records. */
  sees_all?: boolean;
}

export interface SignInResponse {
  /** Send as `Authorization: Bearer <token>` on every later request. */
  token: string;
  expires_at: string;
  officer: CurrentOfficer;
}

export interface MasterOption {
  value: string;
  label: string;
  sort_order: number;
  country: string | null;
  crop: string | null;
}

export interface MasterList {
  list_key: string;
  country: string | null;
  crop: string | null;
  items: MasterOption[];
}

export interface Health {
  status: 'ok' | 'degraded';
  app: string;
  version: string;
  environment: string;
  database: { reachable: boolean; dialect: string };
  server_time: string;
}

/** A delivery site (ginner for cotton, processor for hemp). Shared by Modules 5 to 7. */
export interface Site {
  id: string;
  code: string;
  name: string;
  type: 'ginner' | 'processor';
  crop: 'cotton' | 'hemp';
  country: string;
  address: string | null;
  region: string | null;
  is_dummy: boolean;
  active: boolean;
}
