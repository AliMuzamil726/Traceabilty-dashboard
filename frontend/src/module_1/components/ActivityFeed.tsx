import { History } from 'lucide-react';
import { Link as RouterLink } from 'react-router-dom';
import { formatDateTime } from '@/core/utils/format';
import { EmptyState } from '@/design-system/components/EmptyState';
import { Select } from '@/design-system/components/Select';
import type { Activity } from '../api/types';
import { relativeTime } from '../lib/format';
import { toHref } from '../lib/links';
import { SectionCard } from './SectionCard';

export interface ActivityFeedProps {
  data: Activity | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  module: number | null;
  onModuleChange: (module: number | null) => void;
}

/**
 * The audit log across every module: who changed what, which record, and how long ago.
 * Each line links to the record, so the feed is a way into the work rather than a log
 * to read.
 */
export function ActivityFeed({
  data,
  loading,
  error,
  onRetry,
  module,
  onModuleChange,
}: ActivityFeedProps) {
  const modules = data?.modules ?? [];
  return (
    <SectionCard
      id="activity-heading"
      title="Recent activity"
      description="Every change recorded across the programme."
      loading={loading && !data}
      error={error}
      onRetry={onRetry}
      skeletonHeight="h-64"
      actions={
        <Select
          aria-label="Filter activity by module"
          value={module === null ? '' : String(module)}
          onChange={(e) => onModuleChange(e.target.value === '' ? null : Number(e.target.value))}
          options={[
            { value: '', label: 'Every module' },
            ...modules.map((m) => ({ value: String(m.number), label: m.name })),
          ]}
          className="h-9 w-[168px]"
        />
      }
    >
      {data && data.items.length === 0 ? (
        <EmptyState
          compact
          icon={<History />}
          title="Nothing recorded yet"
          description="Changes appear here as officers register farmers and fill in fieldbooks."
        />
      ) : (
        <ol className="flex flex-col">
          {(data?.items ?? []).map((item) => (
            <li key={item.id} className="border-b border-line/60 py-2.5 last:border-0 last:pb-0">
              <RouterLink to={toHref(item.link)} className="group flex flex-col gap-0.5">
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-medium text-ink group-hover:underline">
                    {item.summary}
                  </span>
                  <span className="text-xs text-muted">{item.module_name}</span>
                </span>
                <span className="text-sm text-muted">
                  {item.officer_name ?? 'System'}
                  {' · '}
                  <time dateTime={item.at} title={formatDateTime(item.at)}>
                    {relativeTime(item.at)}
                  </time>
                </span>
              </RouterLink>
            </li>
          ))}
        </ol>
      )}
    </SectionCard>
  );
}
