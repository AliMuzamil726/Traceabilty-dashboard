import { ArrowRight } from 'lucide-react';
import { cn } from '@/core/utils/cn';

/** What the audit log stores per field: a before and an after. */
export type DiffEntry = { from?: unknown; to?: unknown } | unknown;

export interface DiffViewProps {
  /** `{ field: { from, to } }`, as `core.audit.compute_diff` writes it. */
  diff: Record<string, DiffEntry>;
  className?: string;
  /** Hide the "was" column when there is nothing before (a created record). */
  compact?: boolean;
}

function plain(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function readable(field: string): string {
  const words = field.replace(/_/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * The before and after of one change, as a small table.
 *
 * Used by the audit log and the settings history. A value that is only an "after" (a
 * record being created) shows one column, because an empty "was" column reads as a
 * value that was deleted.
 */
export function DiffView({ diff, className, compact }: DiffViewProps) {
  const rows = Object.entries(diff ?? {});
  if (rows.length === 0) {
    return <p className={cn('text-sm text-muted', className)}>No field changed.</p>;
  }

  return (
    <dl className={cn('grid gap-2 text-sm sm:grid-cols-[minmax(0,10rem)_1fr]', className)}>
      {rows.map(([field, entry]) => {
        const pair =
          entry !== null && typeof entry === 'object' && ('from' in entry || 'to' in entry)
            ? (entry as { from?: unknown; to?: unknown })
            : { to: entry };
        const before = plain(pair.from);
        const after = plain(pair.to);
        const showBefore = !compact && before !== '-';
        return (
          <div key={field} className="contents">
            <dt className="truncate font-medium text-muted">{readable(field)}</dt>
            <dd className="flex min-w-0 flex-wrap items-center gap-2 text-ink">
              {showBefore && (
                <>
                  <span className="mono-id break-all rounded-sm bg-canvas px-1.5 py-0.5 text-xs text-muted line-through">
                    {before}
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted" aria-label="became" />
                </>
              )}
              <span className="mono-id break-all rounded-sm bg-forest-50 px-1.5 py-0.5 text-xs">
                {after}
              </span>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
