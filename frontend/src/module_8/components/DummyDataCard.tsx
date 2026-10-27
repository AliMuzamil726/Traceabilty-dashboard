import { Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/core/api/errors';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { ConfirmDialog } from '@/design-system/components/ConfirmDialog';
import { toast } from '@/design-system/components/toastStore';
import { settingsApi, settingsKeys } from '../api/client';
import type { DummyData, DummyRow } from '../api/types';

export interface DummyDataCardProps {
  data: DummyData | undefined;
}

/**
 * The seeded placeholder officers, offices and sites that came with the install.
 *
 * Removing them is offered only for the rows nothing refers to. A dummy officer who has
 * registered a real farmer is part of that farmer's record, so it stays and says why.
 */
export function DummyDataCard({ data }: DummyDataCardProps) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!data) return null;

  const groups: [string, DummyRow[]][] = [
    ['Officers', data.officers],
    ['Field offices', data.offices],
    ['Sites', data.sites],
  ];
  const total = groups.reduce((sum, [, rows]) => sum + rows.length, 0);

  const remove = async () => {
    setBusy(true);
    try {
      const result = await settingsApi.removeDummy();
      toast.success(
        `${result.removed_total} record${result.removed_total === 1 ? '' : 's'} removed`,
        result.kept.length > 0
          ? `${result.kept.length} kept because real work refers to them.`
          : undefined,
      );
      void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
    } catch (error) {
      toast.error(
        'Could not remove the dummy data',
        error instanceof ApiError ? error.message : 'Please try again.',
      );
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  return (
    <Card padding="md">
      <SectionHeader
        title="Dummy data"
        description="Placeholder people and places the install came with."
        actions={
          <Button
            variant="secondary"
            size="sm"
            disabled={data.removable === 0}
            onClick={() => setConfirming(true)}
            leftIcon={<Trash2 className="h-4 w-4" aria-hidden />}
          >
            Remove unused ({data.removable})
          </Button>
        }
      />

      {total === 0 ? (
        <p className="mt-3 text-base text-muted">
          None left. Everything in the product is real data.
        </p>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          {groups.map(([title, rows]) =>
            rows.length === 0 ? null : (
              <div key={title}>
                <p className="text-sm font-medium text-muted">{title}</p>
                <ul className="mt-1 flex flex-wrap gap-2">
                  {rows.map((row) => (
                    <li key={row.id}>
                      <Badge tone={row.usage > 0 ? 'neutral' : 'warning'}>
                        {row.code} {row.usage > 0 ? `(used by ${row.usage})` : '(unused)'}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </div>
            ),
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirming}
        title={`Remove ${data.removable} unused dummy record${data.removable === 1 ? '' : 's'}?`}
        description="Only records that nothing refers to are removed. Anything a real farmer, delivery or heap depends on is kept, and you are told which."
        confirmLabel="Remove them"
        destructive
        loading={busy}
        onCancel={() => setConfirming(false)}
        onConfirm={() => void remove()}
      />
    </Card>
  );
}
