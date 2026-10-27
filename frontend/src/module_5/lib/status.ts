import type { DeliveryStatus, VarianceLevel } from '../api/types';

export const STATUS_LABEL: Record<DeliveryStatus, string> = {
  scheduled: 'Scheduled',
  in_transit: 'In transit',
  delivered: 'Delivered',
  cancelled: 'Cancelled',
};

/** Pills stay in the two-colour palette. */
export const STATUS_CLASSES: Record<DeliveryStatus, string> = {
  scheduled: 'border-wheat-300 bg-wheat-50 text-ink',
  in_transit: 'border-forest-600 bg-forest-50 text-forest-900',
  delivered: 'border-forest-700 bg-forest-700 text-white',
  cancelled: 'border-line bg-canvas text-muted',
};

/** Variance colouring: Forest for ok, Wheat for warn, the error red only for flag. */
export const LEVEL_CLASSES: Record<VarianceLevel, string> = {
  ok: 'text-forest-700',
  warn: 'text-wheat-600',
  flag: 'text-danger',
};

export const LEVEL_LABEL: Record<VarianceLevel, string> = { ok: 'Within limits', warn: 'Check', flag: 'Flagged' };

/** Which actions a delivery offers in each status. The server enforces the same machine. */
export function actionsFor(status: DeliveryStatus, canAct: boolean, isAdmin: boolean) {
  return {
    edit: canAct && status === 'scheduled',
    dispatch: canAct && status === 'scheduled',
    receive: canAct && status === 'in_transit',
    cancel: canAct && (status === 'scheduled' || status === 'in_transit'),
    correct: isAdmin && status === 'delivered',
  };
}
