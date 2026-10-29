/** Shapes of /api/v1/gate (snake_case, as sent by the API). Weights are kg. */

export type Crop = 'cotton' | 'hemp';
export type GateStatus = 'pending' | 'accepted' | 'rejected';

export interface GateEntry {
  id: string;
  delivery_id: string;
  delivery_no: string;
  site_id: string;
  site_code: string | null;
  site_name: string | null;
  crop: Crop;
  status: GateStatus;
  arrived_at: string;
  vehicle_no: string;
  driver_name: string;
  gross_weight_kg: number | null;
  tare_weight_kg: number | null;
  net_weight_kg: number | null;
  moisture_pct: number | null;
  accepted_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  note: string | null;
  can_accept: boolean;
  can_reject: boolean;
  /** The delivery's reference weight and the tolerances in force; null once decided. */
  field_weight_kg: number | null;
  estimated_quantity_kg: number | null;
  variance_warn_pct: number | null;
  variance_flag_pct: number | null;
  moisture_warn_pct: number | null;
}

export interface GateEntryPage {
  items: GateEntry[];
  total: number;
}

/** An in-transit delivery heading to the site that has not reached the gate yet. */
export interface InboundLoad {
  delivery_id: string;
  delivery_no: string;
  field_code: string;
  farmer_id: string;
  farmer_name: string | null;
  sawie_id: number | null;
  crop: Crop;
  site_id: string;
  vehicle_no: string;
  driver_name: string;
  dispatched_at: string | null;
  estimated_quantity_kg: number | null;
  field_weight_kg: number | null;
}

export interface GateSummary {
  inbound: number;
  pending: number;
  accepted_today: number;
  rejected_today: number;
  net_kg_today: number;
}

export interface GateAcceptInput {
  gross_weight_kg: number;
  tare_weight_kg: number;
  moisture_pct: number;
  note?: string | null;
}

export interface GateAcceptResult {
  entry: GateEntry;
  warnings: string[];
}
