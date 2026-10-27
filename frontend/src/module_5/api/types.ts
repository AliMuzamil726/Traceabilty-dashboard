/** Shapes of /api/v1/deliveries (snake_case, as sent by the API). Weights are kg. */

export type Crop = 'cotton' | 'hemp';
export type DeliveryStatus = 'scheduled' | 'in_transit' | 'delivered' | 'cancelled';
export type VarianceLevel = 'ok' | 'warn' | 'flag';

export interface SiteRef {
  id: string;
  code: string;
  name: string;
  type: 'ginner' | 'processor' | string;
  country: string;
}

export interface Delivery {
  id: string;
  delivery_no: string;
  pickup_request_id: string;
  farmer_id: string;
  field_id: string;
  field_code: string;
  sawie_id: number | null;
  farmer_name: string | null;
  father_or_farm: string | null;
  location: string;
  district: string | null;
  county: string | null;
  officer_name: string | null;
  crop: Crop;
  season_year: number;
  status: DeliveryStatus;
  site: SiteRef | null;
  heap_id: string | null;
  scheduled_date: string;
  driver_name: string;
  driver_phone: string;
  vehicle_no: string;
  dispatched_at: string | null;
  delivered_at: string | null;
  estimated_quantity_kg: number | null;
  field_weight_kg: number | null;
  weighbridge_weight_kg: number | null;
  weighbridge_maunds: number | null;
  moisture_pct: number | null;
  variance_kg: number | null;
  variance_pct: number | null;
  variance_level: VarianceLevel | null;
  note: string | null;
  cancel_reason: string | null;
  created_at: string;
  updated_at: string;
  can_act: boolean;
}

export interface HistoryItem {
  from_status: DeliveryStatus | null;
  to_status: DeliveryStatus;
  officer_id: string | null;
  officer_name: string | null;
  at: string;
  note: string | null;
}

export interface Thresholds {
  variance_warn_pct: number;
  variance_flag_pct: number;
  moisture_warn_pct: number;
}

export interface DeliveryDetail extends Delivery {
  history: HistoryItem[];
  thresholds: Thresholds;
}

export interface DeliveryPage {
  items: Delivery[];
  total: number;
  page: number;
  page_size: number;
  status_counts: Record<DeliveryStatus, number>;
}

export interface InboxItem {
  request_id: string;
  request_no: string;
  field_id: string;
  field_code: string;
  farmer_id: string;
  sawie_id: number | null;
  farmer_name: string | null;
  location: string;
  officer_name: string | null;
  crop: Crop;
  season_year: number;
  estimated_quantity_kg: number | null;
  quantity_is_estimate: boolean;
  preferred_date: string | null;
  note: string | null;
  requested_at: string;
  can_schedule: boolean;
}

export interface ScheduleInput {
  request_ids: string[];
  site_id: string;
  scheduled_date: string;
  driver_name: string;
  driver_phone: string;
  vehicle_no: string;
  note?: string | null;
}

export interface Skipped {
  pickup_request_id: string;
  field_code: string | null;
  code: string;
  reason: string;
}

export interface Stats {
  requests_waiting: number;
  scheduled: number;
  in_transit: number;
  delivered_this_week: number;
  delivered_this_week_kg: number;
  delivered_this_week_maunds: number | null;
  weight_flags: number;
  week_start: string;
}

export interface TransitionResult {
  delivery: DeliveryDetail;
  warnings: string[];
}
