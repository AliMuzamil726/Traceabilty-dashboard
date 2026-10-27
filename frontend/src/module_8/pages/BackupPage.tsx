import { useQuery, useQueryClient } from '@tanstack/react-query';
import { DatabaseBackup } from 'lucide-react';
import { useState } from 'react';
import { ApiError } from '@/core/api/errors';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { ConfirmDialog } from '@/design-system/components/ConfirmDialog';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { KeyValueList } from '@/design-system/components/KeyValueList';
import { toast } from '@/design-system/components/toastStore';
import { settingsApi, settingsKeys } from '../api/client';
import type { Backup } from '../api/types';
import { BackupTable } from '../components/BackupTable';
import { ConfirmPhraseDialog } from '../components/ConfirmPhraseDialog';

/** Take a copy of the database, and put one back. */
export default function BackupPage() {
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState<Backup | null>(null);
  const [deleting, setDeleting] = useState<Backup | null>(null);

  const status = useQuery({
    queryKey: settingsKeys.backupStatus,
    queryFn: ({ signal }) => settingsApi.backupStatus(signal),
  });
  const backups = useQuery({
    queryKey: settingsKeys.backups,
    queryFn: ({ signal }) => settingsApi.backups(signal),
    enabled: status.data?.supported === true,
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
  const fail = (error: unknown) =>
    toast.error('That did not work', error instanceof ApiError ? error.message : 'Please try again.');

  if (status.data && !status.data.supported) {
    return (
      <div className="flex flex-col gap-4">
        <SectionHeader title="Backup and restore" description="Managed outside SAWIE here." />
        <Card padding="md">
          <p className="text-base text-ink">{status.data.reason}</p>
          <p className="mt-2 text-base text-muted">{status.data.instructions}</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="Backup and restore"
        description="A copy of everything, taken while the product keeps running."
      />

      <Card padding="md">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[14rem] flex-1">
            <FormField label="Note" hint="What this copy is for, so it can be recognised later.">
              <Input
                value={note}
                placeholder="Before the October import"
                onChange={(event) => setNote(event.target.value)}
              />
            </FormField>
          </div>
          <Button
            loading={busy}
            leftIcon={<DatabaseBackup className="h-4 w-4" aria-hidden />}
            onClick={() => {
              setBusy(true);
              void settingsApi
                .createBackup(note)
                .then((made) => {
                  toast.success('Backup taken', made.filename);
                  setNote('');
                  refresh();
                })
                .catch(fail)
                .finally(() => setBusy(false));
            }}
          >
            Take a backup now
          </Button>
        </div>
        {status.data && (
          <div className="mt-4">
            <KeyValueList
              items={[
                { label: 'Database', value: status.data.dialect, mono: true },
                {
                  label: 'Current size',
                  value: status.data.database_bytes
                    ? `${(status.data.database_bytes / (1024 * 1024)).toFixed(1)} MB`
                    : 'Unknown',
                  mono: true,
                },
                { label: 'Folder', value: status.data.directory ?? '-', mono: true },
              ]}
              columns={2}
            />
          </div>
        )}
      </Card>

      <BackupTable
        backups={backups.data ?? []}
        loading={backups.isLoading}
        onRestore={setRestoring}
        onDelete={setDeleting}
      />

      <ConfirmPhraseDialog
        open={restoring !== null}
        onClose={() => setRestoring(null)}
        title="Replace the current data?"
        phrase="RESTORE"
        confirmLabel="Restore this backup"
        loading={busy}
        description={
          <>
            <p>
              Everything recorded since <strong>{restoring?.filename}</strong> was taken will be
              gone: farmers, fieldbooks, deliveries, heaps and codes.
            </p>
            <p className="mt-2">
              A safety copy of the current data is taken first, so this can be undone by restoring
              that copy. While the file is swapped the product refuses new work for a few seconds.
            </p>
          </>
        }
        onConfirm={() => {
          const backup = restoring;
          if (!backup) return;
          setBusy(true);
          void settingsApi
            .restoreBackup(backup.id, 'RESTORE')
            .then((result) => {
              toast.success(
                'Restored',
                `Integrity check: ${result.integrity}. Safety copy: ${result.safety_backup}.`,
              );
              setRestoring(null);
              refresh();
            })
            .catch(fail)
            .finally(() => setBusy(false));
        }}
      />

      <ConfirmDialog
        open={deleting !== null}
        title={`Delete ${deleting?.filename ?? ''}?`}
        description="The file is removed from disk. Any other backup you have is untouched."
        confirmLabel="Delete the file"
        destructive
        onCancel={() => setDeleting(null)}
        onConfirm={() => {
          const backup = deleting;
          setDeleting(null);
          if (!backup) return;
          void settingsApi
            .deleteBackup(backup.id)
            .then(() => {
              toast.success('Backup deleted', backup.filename);
              refresh();
            })
            .catch(fail);
        }}
      />
    </div>
  );
}
