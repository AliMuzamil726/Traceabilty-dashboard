import { Download, RotateCcw, Trash2 } from 'lucide-react';
import { formatDateTime } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { DataTable, type Column } from '@/design-system/components/DataTable';
import { settingsApi } from '../api/client';
import type { Backup } from '../api/types';

export interface BackupTableProps {
  backups: Backup[];
  loading: boolean;
  onRestore: (backup: Backup) => void;
  onDelete: (backup: Backup) => void;
}

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function BackupTable({ backups, loading, onRestore, onDelete }: BackupTableProps) {
  const columns: Column<Backup>[] = [
    {
      key: 'created_at',
      header: 'Taken',
      nowrap: true,
      cell: (row) => formatDateTime(row.created_at),
    },
    { key: 'filename', header: 'File', mono: true, cell: (row) => row.filename },
    { key: 'size', header: 'Size', numeric: true, cell: (row) => size(row.size_bytes) },
    {
      key: 'kind',
      header: 'Kind',
      cell: (row) =>
        row.kind === 'safety' ? (
          <Badge tone="warning">Safety copy</Badge>
        ) : (
          <Badge tone="neutral">Manual</Badge>
        ),
    },
    { key: 'note', header: 'Note', cell: (row) => row.note ?? '-' },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      nowrap: true,
      cell: (row) =>
        row.present ? (
          <span className="flex items-center justify-end gap-1">
            <a
              href={settingsApi.backupDownloadUrl(row.id)}
              className="inline-flex items-center gap-1.5 rounded-control px-2.5 py-1.5 text-sm text-ink hover:bg-canvas"
            >
              <Download className="h-4 w-4" aria-hidden />
              Download
            </a>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRestore(row)}
              leftIcon={<RotateCcw className="h-4 w-4" aria-hidden />}
            >
              Restore
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onDelete(row)}
              leftIcon={<Trash2 className="h-4 w-4" aria-hidden />}
            >
              Delete
            </Button>
          </span>
        ) : (
          <Badge tone="danger">File missing</Badge>
        ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={backups}
      rowKey={(row) => row.id}
      caption="Backups on disk, newest first"
      loading={loading}
      empty={
        <p className="px-4 py-10 text-center text-muted">
          No backup yet. Take one before any large change.
        </p>
      }
    />
  );
}
