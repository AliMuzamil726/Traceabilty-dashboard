import { MapPinned, Plus } from 'lucide-react';
import { cn } from '@/core/utils/cn';
import { formatDecimal } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import type { Field } from '../api/types';

export interface FieldRailProps {
  fields: Field[];
  selectedFieldId: string | null;
  onSelect: (fieldId: string) => void;
  /** The ID the next saved field will get, shown as the draft row. */
  nextFieldId: string;
  drafting: boolean;
  onStartNew: () => void;
  editingFieldId?: string | null;
}

/**
 * The farmer's fields down the left of the map page.
 *
 * Selecting a row flies the map to that field and highlights its row in the table
 * below, so the rail, the map and the table always agree about which field is in
 * focus. The row for the field being drawn carries its reserved ID, so the officer
 * can see what they are about to create before they save it.
 */
export function FieldRail({
  fields,
  selectedFieldId,
  onSelect,
  nextFieldId,
  drafting,
  onStartNew,
  editingFieldId,
}: FieldRailProps) {
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-md font-semibold text-ink">
          Fields
          <span className="ml-2 tabular text-sm font-normal text-muted">{fields.length}</span>
        </h2>
        <Button
          size="sm"
          variant="secondary"
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={onStartNew}
          disabled={drafting}
        >
          Add
        </Button>
      </div>

      <ul className="grid max-h-[260px] min-h-0 flex-1 grid-cols-1 content-start gap-1.5 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">
        {fields.map((field) => {
          const selected = field.id === selectedFieldId;
          const editing = field.id === editingFieldId;
          return (
            <li key={field.id}>
              <button
                type="button"
                onClick={() => onSelect(field.id)}
                aria-current={selected ? 'true' : undefined}
                className={cn(
                  'w-full rounded-control border px-3 py-1.5 text-left transition-[border-color,background-color] duration-fast ease-brand',
                  selected
                    ? 'border-forest-700 bg-forest-50'
                    : 'border-line bg-surface hover:border-forest-500/40',
                )}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="mono-id text-sm font-medium text-ink">{field.field_id}</span>
                  <span
                    className="min-w-0 flex-1 truncate tabular text-xs text-muted"
                    title={`${field.vertex_count} corners`}
                  >
                    {formatDecimal(field.area_acre, 2)} ac · {formatDecimal(field.area_ha, 2)} ha
                  </span>
                  {editing ? (
                    <Badge size="sm" tone="accent">
                      Editing
                    </Badge>
                  ) : (
                    <Badge size="sm" tone="success">
                      Saved
                    </Badge>
                  )}
                </span>
              </button>
            </li>
          );
        })}

        {drafting && (
          <li>
            <div className="rounded-control border border-dashed border-forest-600 bg-forest-50/60 px-3 py-1.5">
              <span className="flex items-center justify-between gap-2">
                <span className="mono-id font-medium text-ink">{nextFieldId}</span>
                <Badge size="sm" tone="neutral">
                  Not saved
                </Badge>
              </span>
              <span className="block text-xs text-muted">
                Draw the boundary on the map, then save it.
              </span>
            </div>
          </li>
        )}

        {fields.length === 0 && !drafting && (
          <li className="col-span-full rounded-card border border-dashed border-line p-4 text-center">
            <MapPinned className="mx-auto h-5 w-5 text-forest-700" aria-hidden />
            <p className="mt-2 text-base font-medium text-ink">No fields yet</p>
            <p className="mt-0.5 text-sm text-muted">
              Draw this farmer&apos;s first boundary on the map.
            </p>
          </li>
        )}
      </ul>
    </div>
  );
}
