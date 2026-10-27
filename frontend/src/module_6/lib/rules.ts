/** Small UI rules for the heap screen. The server enforces the same ones. */
import type { HeapDetail } from '../api/types';

export function validateBaleCount(raw: number | null, canAdd: number): string | null {
  if (raw === null || Number.isNaN(raw)) return 'Enter how many bales were made.';
  if (!Number.isInteger(raw)) return 'Enter a whole number of bales.';
  if (raw < 1) return 'Record at least one bale.';
  if (canAdd === 0) return 'No more bales fit the expected output.';
  if (raw > canAdd) return `At most ${canAdd} more ${canAdd === 1 ? 'bale fits' : 'bales fit'} the expected output.`;
  return null;
}

export type CloseMode = 'close' | 'remainder' | 'none';

/** What the Close button offers: a plain close, a close with remainder (administrators), or nothing. */
export function closeState(heap: HeapDetail): { mode: CloseMode; hint: string | null } {
  if (heap.status !== 'open') return { mode: 'none', hint: 'Closed' };
  if (heap.deliveries.length === 0) return { mode: 'none', hint: 'Add at least one delivery first.' };
  if (heap.permissions.can_close) return { mode: 'close', hint: null };
  if (heap.permissions.can_close_with_remainder) {
    return { mode: 'remainder', hint: `${Number(heap.totals.remaining_output_kg).toLocaleString('en-GB')} kg of output is still expected.` };
  }
  return { mode: 'none', hint: 'Record the remaining bales first. Only an administrator can close with a remainder.' };
}
