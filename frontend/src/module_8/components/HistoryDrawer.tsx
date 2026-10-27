import { Undo2 } from 'lucide-react';
import { formatDateTime } from '@/core/utils/format';
import { Button } from '@/design-system/components/Button';
import { Drawer } from '@/design-system/components/Dialog';
import { DiffView } from '@/design-system/components/DiffView';
import { EmptyState } from '@/design-system/components/EmptyState';
import { Skeleton } from '@/design-system/components/Skeleton';
import { useRestoreSetting, useSettingHistory } from '../hooks/useSettings';

export interface HistoryDrawerProps {
  settingKey: string | null;
  label?: string;
  onClose: () => void;
}

/**
 * Every change to one setting, newest first, with the value it replaced.
 *
 * Restoring puts the old value back as a new change rather than deleting the newer
 * one: the history stays a record of what happened, including the mistake and its
 * correction.
 */
export function HistoryDrawer({ settingKey, label, onClose }: HistoryDrawerProps) {
  const open = settingKey !== null;
  const history = useSettingHistory(settingKey ?? undefined, open);
  const restore = useRestoreSetting();

  return (
    <Drawer open={open} onClose={onClose} title={label ? `History: ${label}` : 'History'}>
      {history.isLoading && (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-16 w-full" shape="block" />
          <Skeleton className="h-16 w-full" shape="block" />
        </div>
      )}

      {history.data?.length === 0 && (
        <EmptyState
          compact
          title="No changes yet"
          description="This setting still has the value the product ships with."
        />
      )}

      <ol className="flex flex-col gap-3">
        {(history.data ?? []).map((entry) => (
          <li key={entry.id} className="rounded-card border border-line p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="text-sm text-muted">
                {formatDateTime(entry.changed_at)}
                {entry.changed_by_name ? ` by ${entry.changed_by_name}` : ''}
              </p>
              <Button
                variant="ghost"
                size="sm"
                loading={restore.isPending}
                onClick={() => restore.mutate(entry.id)}
                leftIcon={<Undo2 className="h-4 w-4" aria-hidden />}
              >
                Restore the old value
              </Button>
            </div>
            <div className="mt-2">
              <DiffView diff={{ value: { from: entry.old_value, to: entry.new_value } }} />
            </div>
            {entry.reason && <p className="mt-2 text-sm text-muted">Reason: {entry.reason}</p>}
          </li>
        ))}
      </ol>
    </Drawer>
  );
}
