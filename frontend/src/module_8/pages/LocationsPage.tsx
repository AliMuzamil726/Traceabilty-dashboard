import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Upload } from 'lucide-react';
import { useState } from 'react';
import { ApiError } from '@/core/api/errors';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { ConfirmDialog } from '@/design-system/components/ConfirmDialog';
import { Dialog } from '@/design-system/components/Dialog';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { SegmentedControl } from '@/design-system/components/SegmentedControl';
import { Select } from '@/design-system/components/Select';
import { Skeleton } from '@/design-system/components/Skeleton';
import { toast } from '@/design-system/components/toastStore';
import { settingsApi, settingsKeys } from '../api/client';
import type { LocationNode } from '../api/types';
import { CsvImportDialog } from '../components/CsvImportDialog';
import { LocationTree } from '../components/LocationTree';

type Country = 'PK' | 'GB';

/** Provinces, districts and tehsils (Pakistan) and postcode areas to counties (UK). */
export default function LocationsPage() {
  const queryClient = useQueryClient();
  const [country, setCountry] = useState<Country>('PK');
  const [adding, setAdding] = useState<{ parent: LocationNode | null; level: string } | null>(null);
  const [renaming, setRenaming] = useState<LocationNode | null>(null);
  const [merging, setMerging] = useState<LocationNode | null>(null);
  const [deleting, setDeleting] = useState<LocationNode | null>(null);
  const [importing, setImporting] = useState(false);

  const tree = useQuery({
    queryKey: settingsKeys.locations(country),
    queryFn: ({ signal }) => settingsApi.locationTree(country, signal),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
  const fail = (error: unknown) =>
    toast.error('Could not save', error instanceof ApiError ? error.message : 'Please try again.');

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="Locations"
        description="Where farmers are. A farmer stores the place by name, so renaming one moves every farmer that names it."
        actions={
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setImporting(true)}
              leftIcon={<Upload className="h-4 w-4" aria-hidden />}
            >
              Import
            </Button>
            <a
              href={settingsApi.locationsCsvUrl(country)}
              className="inline-flex items-center gap-1.5 rounded-control px-2.5 py-1.5 text-sm text-ink hover:bg-canvas"
            >
              <Download className="h-4 w-4" aria-hidden />
              Export
            </a>
          </div>
        }
      />

      <SegmentedControl
        aria-label="Country"
        value={country}
        onChange={(value) => setCountry(value)}
        options={[
          { value: 'PK', label: 'Pakistan' },
          { value: 'GB', label: 'United Kingdom' },
        ]}
      />

      <Card padding="md">
        {tree.isLoading ? (
          <Skeleton className="h-64 w-full" shape="block" />
        ) : tree.data ? (
          <LocationTree
            tree={tree.data}
            onAdd={(parent, level) => setAdding({ parent, level })}
            onRename={setRenaming}
            onDelete={setDeleting}
            onMerge={setMerging}
          />
        ) : null}
      </Card>

      <AddDialog
        open={adding !== null}
        parent={adding?.parent ?? null}
        level={adding?.level ?? ''}
        levelLabel={tree.data?.labels[adding?.level ?? ''] ?? adding?.level ?? ''}
        country={country}
        onClose={() => setAdding(null)}
        onSaved={refresh}
      />

      <RenameDialog
        node={renaming}
        onClose={() => setRenaming(null)}
        onSaved={refresh}
        onError={fail}
      />

      <MergeDialog
        node={merging}
        tree={tree.data}
        onClose={() => setMerging(null)}
        onSaved={refresh}
        onError={fail}
      />

      <ConfirmDialog
        open={deleting !== null}
        title={`Delete ${deleting?.name ?? ''}?`}
        description={
          deleting && deleting.usage > 0
            ? `${deleting.usage} farmer(s) name this place, so it cannot be deleted. Merge it into another place instead, which moves them.`
            : 'No farmer names this place, so it can be removed.'
        }
        confirmLabel={deleting && deleting.usage > 0 ? 'Close' : 'Delete the place'}
        destructive={!deleting || deleting.usage === 0}
        onCancel={() => setDeleting(null)}
        onConfirm={() => {
          const node = deleting;
          setDeleting(null);
          if (!node || node.usage > 0) return;
          void settingsApi
            .deleteLocation(node.id)
            .then(() => {
              toast.success('Place deleted', node.name);
              refresh();
            })
            .catch(fail);
        }}
      />

      <CsvImportDialog
        open={importing}
        onClose={() => setImporting(false)}
        title={`Import locations for ${country}`}
        columns={['code', 'name', 'level', 'parent_code']}
        onImport={(text, dryRun) => settingsApi.importLocations(text, dryRun)}
        onDone={refresh}
      />
    </div>
  );
}

function AddDialog({
  open,
  parent,
  level,
  levelLabel,
  country,
  onClose,
  onSaved,
}: {
  open: boolean;
  parent: LocationNode | null;
  level: string;
  levelLabel: string;
  country: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={parent ? `Add a ${levelLabel.toLowerCase()} in ${parent.name}` : `Add a ${levelLabel.toLowerCase()}`}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            loading={busy}
            disabled={!name.trim()}
            onClick={() => {
              setBusy(true);
              setError(null);
              void settingsApi
                .createLocation({ name: name.trim(), level, parent_id: parent?.id ?? null, country })
                .then(() => {
                  toast.success('Place added', name.trim());
                  setName('');
                  onSaved();
                  onClose();
                })
                .catch((caught: unknown) =>
                  setError(caught instanceof ApiError ? caught.message : 'Could not be saved.'),
                )
                .finally(() => setBusy(false));
            }}
          >
            Add
          </Button>
        </>
      }
    >
      {error && <p className="mb-3 rounded-control bg-danger-tint px-3 py-2 text-sm text-danger">{error}</p>}
      <FormField label="Name" required>
        <Input value={name} onChange={(event) => setName(event.target.value)} />
      </FormField>
    </Dialog>
  );
}

function RenameDialog({
  node,
  onClose,
  onSaved,
  onError,
}: {
  node: LocationNode | null;
  onClose: () => void;
  onSaved: () => void;
  onError: (error: unknown) => void;
}) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  if (node && node.id !== loadedFor) {
    setLoadedFor(node.id);
    setName(node.name);
  }

  return (
    <Dialog
      open={node !== null}
      onClose={() => {
        setLoadedFor(null);
        onClose();
      }}
      title={`Rename ${node?.name ?? ''}`}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            loading={busy}
            disabled={!name.trim() || name.trim() === node?.name}
            onClick={() => {
              if (!node) return;
              setBusy(true);
              void settingsApi
                .updateLocation(node.id, { name: name.trim() })
                .then((result) => {
                  toast.success(
                    'Renamed',
                    result.farmers_updated
                      ? `${result.farmers_updated} farmer record(s) now name ${name.trim()}.`
                      : undefined,
                  );
                  setLoadedFor(null);
                  onSaved();
                  onClose();
                })
                .catch(onError)
                .finally(() => setBusy(false));
            }}
          >
            Rename
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        {node && node.usage > 0 && (
          <p className="rounded-control bg-wheat-50 px-3 py-2 text-sm text-ink">
            {node.usage} farmer record{node.usage === 1 ? '' : 's'} name this place. Renaming it
            updates all of them in one go, and the change is recorded in the audit log.
          </p>
        )}
        <FormField label="New name" required>
          <Input value={name} onChange={(event) => setName(event.target.value)} />
        </FormField>
      </div>
    </Dialog>
  );
}

function MergeDialog({
  node,
  tree,
  onClose,
  onSaved,
  onError,
}: {
  node: LocationNode | null;
  tree: { items: LocationNode[] } | undefined;
  onClose: () => void;
  onSaved: () => void;
  onError: (error: unknown) => void;
}) {
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState(false);

  const siblings: LocationNode[] = [];
  const walk = (nodes: LocationNode[]) => {
    for (const current of nodes) {
      if (node && current.level === node.level && current.id !== node.id) siblings.push(current);
      walk(current.children);
    }
  };
  if (node && tree) walk(tree.items);

  return (
    <Dialog
      open={node !== null}
      onClose={onClose}
      title={`Merge ${node?.name ?? ''} into another place`}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={busy}
            disabled={!target}
            onClick={() => {
              if (!node) return;
              setBusy(true);
              void settingsApi
                .merge(node.id, target)
                .then((result) => {
                  toast.success(
                    'Merged',
                    `${result.farmers_updated} farmer record(s) moved.`,
                  );
                  onSaved();
                  onClose();
                })
                .catch(onError)
                .finally(() => setBusy(false));
            }}
          >
            Merge
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-base text-ink">
          Every farmer that names {node?.name} will name the place you choose instead, and{' '}
          {node?.name} is removed. This cannot be undone from here.
        </p>
        <FormField label="Merge into" required>
          <Select
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            placeholder="Choose a place"
            options={siblings.map((item) => ({ value: item.id, label: item.name }))}
          />
        </FormField>
      </div>
    </Dialog>
  );
}
