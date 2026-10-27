/** Shapes of /api/v1/heaps (snake_case; decimals arrive as strings). */

export type Crop = 'cotton' | 'hemp';

export interface HeapTotals {
  input_kg: string;
  input_maunds: string | null;
  outturn_ratio_pct: string;
  bale_unit_kg: string;
  expected_output_kg: string;
  max_bales: number;
  bales_made: number;
  bales_weight_kg: string;
  input_per_bale_kg: string;
  remaining_input_kg: string;
  remaining_output_kg: string;
  consumed_pct: string;
  can_close: boolean;
  can_add_bales: number;
  expected_shiv_kg: string | null;
  expected_dust_kg: string | null;
}

export interface HeapListItem {
  id: string;
  heap_id: string;
  site_id: string;
  crop: Crop;
  status: 'open' | 'closed';
  opened_at: string;
  closed_at: string | null;
  deliveries: number;
  input_kg: string;
  bales_made: number;
}

export interface HeapMember {
  delivery_id: string;
  delivery_no: string;
  farmer_id: string;
  field_id: string;
  field_code: string;
  sawie_id: number | null;
  farmer_name: string | null;
  village_or_farm: string | null;
  delivered_at: string | null;
  field_weight_kg: number | null;
  weighbridge_weight_kg: number | null;
  moisture_pct: number | null;
}

export interface Contribution {
  farmer_id: string;
  sawie_id: number | null;
  farmer_name: string | null;
  kg: string;
  pct: string;
  deliveries: number;
  fields: number;
}

export interface Bale {
  id: string;
  bale_serial: string;
  seq: number;
  weight_kg: number;
  status: 'active' | 'voided';
  void_reason: string | null;
  created_at: string;
  created_by: string | null;
  voided_at: string | null;
}

export interface PendingDelivery {
  id: string;
  delivery_no: string;
  field_code: string;
  sawie_id: number | null;
  farmer_name: string | null;
  village_or_farm: string | null;
  delivered_at: string | null;
  weighbridge_weight_kg: number | null;
  moisture_pct: number | null;
}

export interface HeapPermissions {
  can_edit_values: boolean;
  can_add_deliveries: boolean;
  can_remove_deliveries: boolean;
  can_record_bales: boolean;
  can_void_bales: boolean;
  can_close: boolean;
  can_close_with_remainder: boolean;
}

export interface HeapDetail {
  id: string;
  heap_id: string;
  crop: Crop;
  status: 'open' | 'closed';
  site: { id: string; code: string; name: string; type: string; address: string | null };
  opened_at: string;
  opened_by_name: string | null;
  closed_at: string | null;
  closed_by_name: string | null;
  close_reason: string | null;
  outturn_ratio_pct: number;
  bale_unit_kg: number;
  shiv_pct: number | null;
  dust_pct: number | null;
  note: string | null;
  totals: HeapTotals;
  deliveries: HeapMember[];
  contributions: Contribution[];
  bales: Bale[];
  pending_deliveries: PendingDelivery[];
  permissions: HeapPermissions;
}

export interface Skipped {
  delivery_id: string;
  delivery_no: string | null;
  code: string;
  reason: string;
}
