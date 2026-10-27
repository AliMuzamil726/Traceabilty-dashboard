import { Map as MapIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/core/utils/cn';
import { formatDecimal } from '@/core/utils/format';
import { Badge, EmptyState, buttonClasses } from '@/design-system/components';
import type { FieldOption } from '../api/types';

export interface FieldCardsProps {
  farmerId: string;
  crop: string;
  fields: FieldOption[];
  value: string | null;
  onChange: (fieldId: string) => void;
}

const BOOK: Record<string, { label: string; tone: 'neutral' | 'warning' | 'success' }> = {
  none: { label: 'No fieldbook', tone: 'neutral' },
  draft: { label: 'Draft', tone: 'warning' },
  submitted: { label: 'Submitted', tone: 'success' },
};

/** The farmer's mapped fields as cards. A farmer with no field is sent to map one. */
export function FieldCards({ farmerId, crop, fields, value, onChange }: FieldCardsProps) {
  if (fields.length === 0) {
    return (
      <EmptyState
        compact
        icon={<MapIcon className="h-5 w-5" />}
        title="This farmer has no mapped field"
        description="A fieldbook belongs to a field. Map the field in Register Farmer first."
        action={
          <Link to={`/register/farmers/${farmerId}/fields/new`} className={buttonClasses('secondary', 'sm')}>
            Add field
          </Link>
        }
      />
    );
  }
  return (
    <div role="radiogroup" aria-label="Field" className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {fields.map((field) => {
        const on = field.id === value;
        const book = BOOK[field.fieldbook_status] ?? BOOK.none!;
        return (
          <button
            key={field.id}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(field.id)}
            className={cn(
              'flex flex-col items-start gap-1 rounded-lg border p-3 text-left',
              on ? 'border-forest-600 bg-forest-50 ring-2 ring-forest-100' : 'border-line bg-surface hover:border-forest-500',
            )}
          >
            <span className="font-mono text-sm font-semibold text-ink">{field.field_id}</span>
            <span className="text-sm text-muted tabular">
              {crop === 'cotton' ? `${formatDecimal(field.area_acre)} acres` : `${formatDecimal(field.area_ha)} ha`}
            </span>
            <Badge size="sm" tone={book.tone}>
              {book.label}
            </Badge>
          </button>
        );
      })}
    </div>
  );
}
