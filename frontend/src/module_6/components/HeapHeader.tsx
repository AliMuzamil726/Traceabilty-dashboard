import { QrCode } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatDate } from '@/core/utils/format';
import { buttonClasses } from '@/design-system/components/buttonStyles';
import type { HeapDetail } from '../api/types';
import { words } from '../lib/wording';
import { HeapStatusPill } from './HeapList';

export function HeapHeader({ heap }: { heap: HeapDetail }) {
  const w = words(heap.crop);
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted">{w.lot}</p>
        <h2 className="font-mono text-xl font-semibold text-ink">{heap.heap_id}</h2>
        <p className="text-sm text-muted">
          {w.site}: {heap.site.name}{heap.site.address ? `, ${heap.site.address}` : ''}
        </p>
        <p className="text-xs text-muted">
          Opened {formatDate(heap.opened_at)}{heap.opened_by_name ? ` by ${heap.opened_by_name}` : ''}
          {heap.closed_at ? `, closed ${formatDate(heap.closed_at)}${heap.closed_by_name ? ` by ${heap.closed_by_name}` : ''}` : ''}
        </p>
        {heap.close_reason && <p className="text-xs text-muted">Close reason: {heap.close_reason}</p>}
      </div>
      <div className="flex flex-col items-end gap-2">
        <HeapStatusPill status={heap.status} />
        <Link
          to={`/qr?crop=${heap.crop}&site=${heap.site.id}&lot=${encodeURIComponent(heap.heap_id)}`}
          className={buttonClasses('ghost', 'sm')}
        >
          <QrCode className="h-4 w-4" aria-hidden />
          QR codes
        </Link>
      </div>
    </div>
  );
}
