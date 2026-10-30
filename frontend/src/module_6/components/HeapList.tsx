import { cn } from '@/core/utils/cn';
import { formatDate } from '@/core/utils/format';
import { EmptyState, Skeleton } from '@/design-system/components';
import type { Crop, HeapListItem } from '../api/types';
import { kgText, words } from '../lib/wording';

export function HeapStatusPill({ status }: { status: 'open' | 'closed' }) {
  return (
    <span className={cn('inline-flex rounded-full border px-2 py-0.5 text-xs font-medium', status === 'open' ? 'border-forest-600 bg-forest-50 text-forest-900' : 'border-line bg-canvas text-muted')}>
      {status === 'open' ? 'Open' : 'Closed'}
    </span>
  );
}

export function HeapList({ crop, heaps, loading, selected, onSelect, siteName }: { crop: Crop; heaps: HeapListItem[]; loading: boolean; selected: string | null; onSelect: (id: string) => void; siteName?: (heap: HeapListItem) => string | null }) {
  const w = words(crop);
  if (loading && !heaps.length) return <Skeleton className="h-64 w-full" shape="block" />;
  if (!heaps.length) return <EmptyState compact title={`No ${w.lots.toLowerCase()}`} description={`Open a ${w.lotLower} to start gathering deliveries.`} />;
  return (
    <ul aria-label={w.lots} className="flex flex-col gap-1.5">
      {heaps.map((h) => {
        const site = siteName?.(h);
        return (
        <li key={h.id}>
          <button type="button" aria-current={selected === h.id || undefined} onClick={() => onSelect(h.id)}
            className={cn('flex w-full flex-col gap-1 rounded-control border px-3 py-2 text-left', selected === h.id ? 'border-forest-700 bg-forest-50' : 'border-line bg-surface hover:border-forest-500')}>
            <span className="flex items-center justify-between gap-2">
              <span className="font-mono text-sm font-semibold text-ink">{h.heap_id}</span>
              <HeapStatusPill status={h.status} />
            </span>
            {site && <span className="text-xs text-ink">{site}</span>}
            <span className="text-xs text-muted">
              {h.deliveries} {h.deliveries === 1 ? 'delivery' : 'deliveries'}, {kgText(h.input_kg)}, opened {formatDate(h.opened_at)}
            </span>
          </button>
        </li>
        );
      })}
    </ul>
  );
}
