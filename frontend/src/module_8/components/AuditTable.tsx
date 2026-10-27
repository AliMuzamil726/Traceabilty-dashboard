import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/core/utils/cn';
import { formatDateTime } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { DiffView } from '@/design-system/components/DiffView';
import { EmptyState } from '@/design-system/components/EmptyState';
import { Skeleton } from '@/design-system/components/Skeleton';
import type { AuditEntry, AuditPage } from '../api/types';

export interface AuditTableProps {
  page: AuditPage | undefined;
  loading: boolean;
  onPageChange: (page: number) => void;
}

const ACTION_TONE: Record<string, 'success' | 'info' | 'danger' | 'neutral'> = {
  create: 'success',
  update: 'info',
  delete: 'danger',
  state_change: 'neutral',
};

/**
 * The audit log, one page at a time, with the before and after of each change.
 *
 * Nothing here edits or deletes an entry, and no route in the product offers it: a log
 * that can be changed proves nothing about what happened.
 */
export function AuditTable({ page, loading, onPageChange }: AuditTableProps) {
  if (loading && !page) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-14 w-full" shape="block" />
        ))}
      </div>
    );
  }
  if (!page || page.items.length === 0) {
    return (
      <EmptyState
        title="Nothing matches"
        description="Change the filters, or widen the dates. Every change officers make is recorded here."
      />
    );
  }

  const pages = Math.max(1, Math.ceil(page.total / page.page_size));
  return (
    <div className="flex flex-col gap-3">
      <ul className="divide-y divide-line rounded-card border border-line">
        {page.items.map((entry) => (
          <AuditRow key={entry.id} entry={entry} />
        ))}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
        <span>
          {page.total.toLocaleString()} entr{page.total === 1 ? 'y' : 'ies'}, page {page.page} of{' '}
          {pages}
        </span>
        <span className="flex items-center gap-2">
          <button
            type="button"
            className="rounded-control border border-line px-3 py-1.5 disabled:opacity-50"
            disabled={page.page <= 1}
            onClick={() => onPageChange(page.page - 1)}
          >
            Previous
          </button>
          <button
            type="button"
            className="rounded-control border border-line px-3 py-1.5 disabled:opacity-50"
            disabled={page.page >= pages}
            onClick={() => onPageChange(page.page + 1)}
          >
            Next
          </button>
        </span>
      </div>
    </div>
  );
}

function AuditRow({ entry }: { entry: AuditEntry }) {
  const [open, setOpen] = useState(false);
  const fields = Object.keys(entry.diff ?? {}).length;

  return (
    <li className="bg-surface">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5 text-left hover:bg-canvas"
      >
        <span className="tabular w-40 shrink-0 text-sm text-muted">
          {formatDateTime(entry.created_at)}
        </span>
        <Badge tone={ACTION_TONE[entry.action] ?? 'neutral'}>{entry.action.replace('_', ' ')}</Badge>
        <span className="min-w-0 flex-1 truncate text-base text-ink">
          {entry.entity.replace(/_/g, ' ')}{' '}
          <span className="mono-id text-sm text-muted">{entry.entity_id}</span>
        </span>
        <span className="text-sm text-muted">{entry.officer_name ?? 'System'}</span>
        <ChevronDown
          className={cn('h-4 w-4 shrink-0 text-muted transition-transform duration-fast', open && 'rotate-180')}
          aria-hidden
        />
      </button>
      {open && (
        <div className="border-t border-line bg-canvas px-3 py-3">
          {fields === 0 ? (
            <p className="text-sm text-muted">No field-level detail was recorded for this entry.</p>
          ) : (
            <DiffView diff={entry.diff} compact={entry.action === 'create'} />
          )}
        </div>
      )}
    </li>
  );
}
