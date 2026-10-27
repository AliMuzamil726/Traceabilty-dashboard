import { cn } from '@/core/utils/cn';
import { formatDate } from '@/core/utils/format';
import { Button, EmptyState, Skeleton } from '@/design-system/components';
import type { Delivery, DeliveryStatus } from '../api/types';
import { STATUS_CLASSES, STATUS_LABEL } from '../lib/status';

export interface DeliveryListProps {
  items: Delivery[];
  counts: Record<DeliveryStatus, number> | undefined;
  status: string;
  onStatus: (status: string) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  page: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
}

export function StatusPill({ status }: { status: DeliveryStatus }) {
  return <span className={cn('inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium', STATUS_CLASSES[status])}>{STATUS_LABEL[status]}</span>;
}

export function DeliveryList({ items, counts, status, onStatus, selectedId, onSelect, loading, page, total, pageSize, onPage }: DeliveryListProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex flex-col gap-3">
      <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-1.5">
        {(['', 'scheduled', 'in_transit', 'delivered', 'cancelled'] as const).map((s) => {
          const on = status === s;
          const count = s ? counts?.[s] : counts ? Object.values(counts).reduce((a, b) => a + b, 0) : undefined;
          return (
            <button key={s || 'all'} type="button" aria-pressed={on} onClick={() => onStatus(s)}
              className={cn('rounded-full border px-3 py-1 text-xs font-medium', on ? 'border-forest-700 bg-forest-700 text-white' : 'border-line bg-surface text-ink hover:border-forest-500')}>
              {s ? STATUS_LABEL[s] : 'All'} {count !== undefined && <span className="tabular">{count}</span>}
            </button>
          );
        })}
      </div>
      {loading && !items.length ? (
        <Skeleton className="h-64 w-full" shape="block" />
      ) : items.length === 0 ? (
        <EmptyState compact title="No deliveries" description="Schedule requests from the inbox, or change the filters." />
      ) : (
        <ul aria-label="In transit loads" className="flex flex-col gap-1.5">
          {items.map((d) => (
            <li key={d.id}>
              <button type="button" aria-current={selectedId === d.id || undefined} onClick={() => onSelect(d.id)}
                className={cn('flex w-full flex-col gap-1 rounded-control border px-3 py-2 text-left', selectedId === d.id ? 'border-forest-700 bg-forest-50' : 'border-line bg-surface hover:border-forest-500')}>
                <span className="flex items-center justify-between gap-2">
                  <span className="font-mono text-sm font-semibold text-ink">{d.delivery_no}</span>
                  <StatusPill status={d.status} />
                </span>
                <span className="truncate text-sm text-ink">{d.farmer_name ?? '-'} <span className="text-muted">field {d.field_code}</span></span>
                <span className="text-xs text-muted">{formatDate(d.scheduled_date)}, {d.site?.code ?? '-'}, {d.vehicle_no}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {pages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted">
          <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
          <span>Page {page} of {pages}</span>
          <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
        </div>
      )}
    </div>
  );
}
