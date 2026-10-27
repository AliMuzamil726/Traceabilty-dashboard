import { Card, Skeleton } from '@/design-system/components';
import { formatDateTime } from '@/core/utils/format';
import type { TimelineItem } from '../api/types';

export interface ActivityTimelineProps {
  items: TimelineItem[] | undefined;
  loading?: boolean;
  limit?: number;
}

/** Newest first: what was recorded, when, and by whom. */
export function ActivityTimeline({ items, loading, limit = 12 }: ActivityTimelineProps) {
  return (
    <Card padding="md" aria-label="Activity">
      <h3 className="text-sm font-semibold text-ink">Activity</h3>
      {loading && !items ? (
        <div className="mt-3 flex flex-col gap-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ) : (
        <ol className="mt-3 flex flex-col gap-3">
          {(items ?? []).slice(0, limit).map((item, i) => (
            <li key={`${item.at}-${i}`} className="relative border-l border-line pl-3">
              <span className="absolute -left-[4px] top-1.5 h-2 w-2 rounded-full bg-forest-600" aria-hidden />
              <p className="text-sm text-ink">
                {item.step_title && <span className="font-medium">{item.step_title}: </span>}
                {item.summary}
              </p>
              <p className="text-xs text-muted">
                {formatDateTime(item.at)}
                {item.officer_name ? `, ${item.officer_name}` : ''}
              </p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
