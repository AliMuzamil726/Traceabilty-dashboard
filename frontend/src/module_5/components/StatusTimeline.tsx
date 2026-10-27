import { formatDateTime } from '@/core/utils/format';
import type { HistoryItem } from '../api/types';
import { STATUS_LABEL } from '../lib/status';

export function StatusTimeline({ history }: { history: HistoryItem[] }) {
  return (
    <ol aria-label="Status history" className="flex flex-col gap-3">
      {history.map((h, i) => (
        <li key={`${h.at}-${i}`} className="relative border-l border-line pl-3">
          <span className="absolute -left-[4px] top-1.5 h-2 w-2 rounded-full bg-forest-600" aria-hidden />
          <p className="text-sm font-medium text-ink">
            {h.from_status === h.to_status ? 'Corrected' : STATUS_LABEL[h.to_status]}
          </p>
          <p className="text-xs text-muted">{formatDateTime(h.at)}{h.officer_name ? `, ${h.officer_name}` : ''}</p>
          {h.note && <p className="text-sm text-muted">{h.note}</p>}
        </li>
      ))}
    </ol>
  );
}
