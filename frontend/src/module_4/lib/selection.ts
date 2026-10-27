import type { RadarRow } from '../api/types';

/**
 * Why the selected fields cannot all be requested. Empty means Request pickup may be
 * pressed. Uses only what the server already decided per row (status, open request,
 * whether this officer may act); it does not re-derive readiness.
 */
export function requestBlockers(rows: RadarRow[]): string[] {
  if (rows.length === 0) return ['Select at least one field.'];
  const reasons: string[] = [];
  const notReady = rows.filter((r) => r.status !== 'ready' && r.status !== 'harvested');
  const open = rows.filter((r) => r.pickup_state === 'requested' || r.pickup_state === 'scheduled');
  const notMine = rows.filter((r) => !r.can_act);
  const list = (rs: RadarRow[]) => rs.slice(0, 3).map((r) => r.field_code).join(', ') + (rs.length > 3 ? ` and ${rs.length - 3} more` : '');
  if (notReady.length) reasons.push(`Not ready or harvested: ${list(notReady)}`);
  if (open.length) reasons.push(`Pickup already requested: ${list(open)}`);
  if (notMine.length) reasons.push(`Another officer's farmer: ${list(notMine)}`);
  return reasons;
}

export function areaOf(row: RadarRow, unit: 'acre' | 'ha'): number {
  return unit === 'acre' ? row.area_acre : row.area_ha;
}
