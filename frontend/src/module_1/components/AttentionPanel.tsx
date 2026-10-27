import { CircleCheck } from 'lucide-react';
import { formatNumber } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { EmptyState } from '@/design-system/components/EmptyState';
import type { Alerts } from '../api/types';
import { AlertRow } from './AlertRow';
import { SectionCard } from './SectionCard';

export interface AttentionPanelProps {
  data: Alerts | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
}

/**
 * What needs a person. Rules that found nothing are left out, so the panel is a list
 * of things to do rather than a list of rules, and an empty panel means an empty
 * panel. Critical rules come first.
 */
export function AttentionPanel({ data, loading, error, onRetry }: AttentionPanelProps) {
  const raised = (data?.alerts ?? [])
    .filter((alert) => alert.count > 0)
    .sort((a, b) => {
      if (a.severity !== b.severity) return a.severity === 'critical' ? -1 : 1;
      return b.count - a.count;
    });

  return (
    <SectionCard
      id="attention-heading"
      title="Needs attention"
      description="Rules checked against every module, newest problems first."
      loading={loading && !data}
      error={error}
      onRetry={onRetry}
      skeletonHeight="h-64"
      actions={
        data ? (
          <div className="flex items-center gap-2">
            {data.critical > 0 && (
              <Badge tone="danger" size="sm">
                {formatNumber(data.critical)} critical
              </Badge>
            )}
            <Badge tone={data.total > 0 ? 'warning' : 'success'} size="sm">
              {formatNumber(data.total)} in all
            </Badge>
          </div>
        ) : undefined
      }
    >
      {raised.length === 0 ? (
        <EmptyState
          compact
          icon={<CircleCheck />}
          title="Nothing needs attention"
          description="Every rule is clear for this crop and season."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {raised.map((alert, index) => (
            <AlertRow key={alert.key} alert={alert} index={index} />
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
