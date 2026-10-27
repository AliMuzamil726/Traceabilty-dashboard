/** Small display helpers shared by the module's components and pages. */

import { formatDate } from '@/core/utils/format';
import type { FarmerOption, FieldDef } from '../api/types';
import { isEmpty, type LabelOf } from './schemaLogic';

export function farmerLabel(f: Pick<FarmerOption, 'sawie_id' | 'name'>): string {
  return `${f.sawie_id}, ${f.name}`;
}

export function bookPath(bookId: string, locked: boolean): string {
  return locked ? `/fieldbook/books/${bookId}/view` : `/fieldbook/books/${bookId}`;
}

export function formatAnswer(field: FieldDef, value: unknown, labelOf: LabelOf): string {
  if (isEmpty(value)) return '-';
  if (field.list_key && typeof value === 'string') return labelOf(field.list_key, value);
  if (field.list_key && Array.isArray(value)) return value.map((v) => labelOf(field.list_key as string, String(v))).join(', ');
  if (field.type === 'date' && typeof value === 'string') return formatDate(value);
  if (field.type === 'dates' && Array.isArray(value)) return value.map((v) => formatDate(String(v))).join(', ');
  if (field.type === 'paired_number' && typeof value === 'object') {
    return (field.parts ?? [])
      .map((p) => `${p.label} ${(value as Record<string, unknown>)[p.key] ?? '-'}${p.unit ? ` ${p.unit}` : ''}`)
      .join(', ');
  }
  if (typeof value === 'number') return `${Math.round(value * 100) / 100}${field.unit ? ` ${field.unit}` : ''}`;
  return String(value);
}
