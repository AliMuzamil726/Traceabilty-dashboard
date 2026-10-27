import { Reorder, useDragControls } from 'framer-motion';
import { Download, GripVertical, Plus, Trash2, Upload } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/core/api/errors';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { ConfirmDialog } from '@/design-system/components/ConfirmDialog';
import { EmptyState } from '@/design-system/components/EmptyState';
import { IconButton } from '@/design-system/components/IconButton';
import { Input } from '@/design-system/components/Input';
import { Skeleton } from '@/design-system/components/Skeleton';
import { Switch } from '@/design-system/components/Switch';
import { toast } from '@/design-system/components/toastStore';
import { settingsApi, settingsKeys } from '../api/client';
import type { ListSummary, ListValue } from '../api/types';
import { CsvImportDialog } from './CsvImportDialog';

export interface ListManagerProps {
  list: ListSummary;
  values: ListValue[];
  loading: boolean;
  onChanged: () => void;
}

/**
 * The values of one dropdown list.
 *
 * Three rules are visible on this screen rather than explained in a manual: a label can
 * always be corrected because records store the key beside it; deactivating takes a
 * value out of new forms and leaves every existing record alone; and deleting is
 * offered only while nothing uses the value.
 */
export function ListManager({ list, values, loading, onChanged }: ListManagerProps) {
  const queryClient = useQueryClient();
  const [order, setOrder] = useState<ListValue[]>(values);
  const [adding, setAdding] = useState('');
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<ListValue | null>(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => setOrder(values), [values]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
    onChanged();
  };

  const fail = (error: unknown) =>
    toast.error(
      'Could not save',
      error instanceof ApiError ? error.message : 'Please try again.',
    );

  const add = async () => {
    const label = adding.trim();
    if (!label) return;
    setBusy(true);
    try {
      await settingsApi.addListValue(list.key, { label });
      setAdding('');
      toast.success('Value added', label);
      refresh();
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  };

  const saveOrder = async (next: ListValue[]) => {
    try {
      await settingsApi.reorderList(
        list.key,
        next.map((row) => row.id),
      );
      refresh();
    } catch (error) {
      fail(error);
      setOrder(values);
    }
  };

  const setActive = async (row: ListValue, active: boolean) => {
    try {
      await settingsApi.updateListValue(list.key, row.id, { active });
      refresh();
    } catch (error) {
      fail(error);
    }
  };

  const rename = async (row: ListValue, label: string) => {
    if (label.trim() === row.label || !label.trim()) return;
    try {
      await settingsApi.updateListValue(list.key, row.id, { label: label.trim() });
      refresh();
    } catch (error) {
      fail(error);
    }
  };

  return (
    <Card padding="md" className="min-w-0">
      <SectionHeader
        title={list.label}
        description={
          list.required_by.length > 0
            ? `Required by ${list.required_by.join(', ')}.`
            : 'Used by the forms that reference it.'
        }
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
              href={settingsApi.listCsvUrl(list.key)}
              className="inline-flex items-center gap-1.5 rounded-control px-2.5 py-1.5 text-sm text-ink hover:bg-canvas"
            >
              <Download className="h-4 w-4" aria-hidden />
              Export
            </a>
          </div>
        }
      />

      <div className="mt-4 flex flex-wrap items-end gap-2">
        <div className="min-w-[12rem] flex-1">
          <label htmlFor={`add-${list.key}`} className="mb-1 block text-sm font-medium text-muted">
            Add a value
          </label>
          <Input
            id={`add-${list.key}`}
            value={adding}
            placeholder="What an officer will see in the dropdown"
            onChange={(event) => setAdding(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void add();
            }}
          />
        </div>
        <Button
          onClick={() => void add()}
          loading={busy}
          disabled={!adding.trim()}
          leftIcon={<Plus className="h-4 w-4" aria-hidden />}
        >
          Add
        </Button>
      </div>

      {loading ? (
        <div className="mt-4 flex flex-col gap-2">
          <Skeleton className="h-12 w-full" shape="block" />
          <Skeleton className="h-12 w-full" shape="block" />
        </div>
      ) : order.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            compact
            title="This list is empty"
            description="Add the first value above. It appears in the forms that use this list."
          />
        </div>
      ) : (
        <>
          <p className="mt-4 text-sm text-muted">
            Drag a value to change the order officers see. The order is saved when you drop it.
          </p>
          <Reorder.Group
            axis="y"
            values={order}
            onReorder={setOrder}
            className="mt-2 flex flex-col divide-y divide-line rounded-card border border-line"
          >
            {order.map((row) => (
              <ValueRow
                key={row.id}
                row={row}
                onDrop={() => void saveOrder(order)}
                onRename={(label) => void rename(row, label)}
                onActiveChange={(active) => void setActive(row, active)}
                onDelete={() => setToDelete(row)}
              />
            ))}
          </Reorder.Group>
        </>
      )}

      <ConfirmDialog
        open={toDelete !== null}
        title={`Delete ${toDelete?.label ?? ''}?`}
        description="Nothing uses this value, so deleting it removes it for good. To keep it on existing records but hide it from new ones, deactivate it instead."
        confirmLabel="Delete the value"
        destructive
        onCancel={() => setToDelete(null)}
        onConfirm={() => {
          const row = toDelete;
          setToDelete(null);
          if (!row) return;
          void settingsApi
            .deleteListValue(list.key, row.id)
            .then(() => {
              toast.success('Value deleted', row.label);
              refresh();
            })
            .catch(fail);
        }}
      />

      <CsvImportDialog
        open={importing}
        onClose={() => setImporting(false)}
        title={`Import values into ${list.label}`}
        columns={['value', 'label', 'active']}
        onImport={(text, dryRun) => settingsApi.importList(list.key, text, dryRun)}
        onDone={refresh}
      />
    </Card>
  );
}

interface ValueRowProps {
  row: ListValue;
  onDrop: () => void;
  onRename: (label: string) => void;
  onActiveChange: (active: boolean) => void;
  onDelete: () => void;
}

function ValueRow({ row, onDrop, onRename, onActiveChange, onDelete }: ValueRowProps) {
  const controls = useDragControls();
  const [label, setLabel] = useState(row.label);
  useEffect(() => setLabel(row.label), [row.label]);

  return (
    <Reorder.Item
      value={row}
      dragListener={false}
      dragControls={controls}
      onDragEnd={onDrop}
      className="flex flex-wrap items-center gap-3 bg-surface p-3"
    >
      <button
        type="button"
        aria-label={`Reorder ${row.label}`}
        onPointerDown={(event) => controls.start(event)}
        className="cursor-grab touch-none rounded-control p-1 text-muted hover:bg-canvas active:cursor-grabbing"
      >
        <GripVertical className="h-4 w-4" aria-hidden />
      </button>

      <div className="min-w-[10rem] flex-1">
        <Input
          aria-label={`Label for ${row.value}`}
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          onBlur={() => onRename(label)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') (event.target as HTMLInputElement).blur();
          }}
        />
        <p className="mt-1 text-xs text-muted">
          Stored as <span className="mono-id">{row.value}</span>
          {row.usage > 0 && ` - used by ${row.usage} record${row.usage === 1 ? '' : 's'}`}
        </p>
      </div>

      <Switch
        checked={row.active}
        onChange={onActiveChange}
        label={`${row.label} is available in new forms`}
        hideLabel
      />

      {row.can_delete ? (
        <IconButton
          label={`Delete ${row.label}`}
          icon={<Trash2 className="h-4 w-4" />}
          onClick={onDelete}
        />
      ) : (
        <Badge tone="neutral">In use</Badge>
      )}
    </Reorder.Item>
  );
}
