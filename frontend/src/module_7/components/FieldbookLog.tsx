import { formatDateTime } from '@/core/utils/format';
import { Badge, EmptyState } from '@/design-system/components';
import type { TraceField } from '../api/types';

/** Everything recorded in the field's fieldbook, oldest first, with who recorded it. */
export function FieldbookLog({ field }: { field: TraceField }) {
  const book = field.fieldbook;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="mono-id font-medium text-ink">{field.field_code}</span>
        <span className="text-muted">season {field.season_year}</span>
        {book
          ? <Badge size="sm" tone={book.status === 'submitted' ? 'success' : 'warning'}>
              {book.status === 'submitted' ? 'Submitted' : `Draft, ${book.steps_complete} of ${book.steps_total} steps`}
            </Badge>
          : <Badge size="sm" tone="warning">No fieldbook</Badge>}
      </div>
      {field.log.length === 0 ? (
        <EmptyState compact title="Nothing recorded" />
      ) : (
        <ol aria-label={`Fieldbook log for ${field.field_code}`} className="flex flex-col divide-y divide-line rounded-card border border-line">
          {field.log.map((e, i) => (
            <li key={`${e.at}-${i}`} className="flex flex-col gap-0.5 px-3 py-2 sm:flex-row sm:items-baseline sm:gap-3">
              <span className="w-40 shrink-0 text-xs tabular-nums text-muted">{formatDateTime(e.at)}</span>
              <span className="w-44 shrink-0 text-sm font-medium text-ink">{e.step}</span>
              <span className="min-w-0 flex-1 text-sm text-ink">{e.summary}</span>
              <span className="shrink-0 text-xs text-muted">{e.officer ?? ''}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
