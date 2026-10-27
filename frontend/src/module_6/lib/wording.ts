import type { Crop } from '../api/types';

/** Cotton is gathered in heaps at ginners; hemp in batches at processors. */
export function words(crop: Crop) {
  return crop === 'cotton'
    ? { lot: 'Heap', lots: 'Heaps', lotLower: 'heap', site: 'Ginner', siteLower: 'ginner', output: 'lint' }
    : { lot: 'Batch', lots: 'Batches', lotLower: 'batch', site: 'Processor', siteLower: 'processor', output: 'fibre' };
}

/** "17,000.00" style for kg strings from the API; maunds for cotton. */
export function kgText(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '-';
  return `${Number(value).toLocaleString('en-GB', { maximumFractionDigits: 2 })} kg`;
}
