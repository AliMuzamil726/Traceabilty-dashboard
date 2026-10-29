import { Crosshair, List, Pencil, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { formatDecimal } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { ConfirmDialog } from '@/design-system/components/ConfirmDialog';
import { DataTable, type Column } from '@/design-system/components/DataTable';
import { IconButton } from '@/design-system/components/IconButton';
import type { Field } from '../api/types';
import { formatLatLng } from '../format';

export interface FieldTableProps {
  fields: Field[];
  loading?: boolean;
  selectedFieldId: string | null;
  onSelect: (fieldId: string) => void;
  onLocate: (field: Field) => void;
  onEdit: (field: Field) => void;
  onDelete: (field: Field) => void;
  onShowVertices: (field: Field) => void;
  deleting?: boolean;
}

/**
 * This farmer's fields in full: both areas, the corner count, the centroid, the pin
 * and the row actions.
 *
 * Both area units are shown rather than one per programme, because a cotton officer
 * reporting to a UK buyer needs hectares and a UK grower reads acres on a farm map.
 * Deleting asks first and names the field, since a field carries a QR trail later.
 */
export function FieldTable({
  fields,
  loading,
  selectedFieldId,
  onSelect,
  onLocate,
  onEdit,
  onDelete,
  onShowVertices,
  deleting,
}: FieldTableProps) {
  const [pendingDelete, setPendingDelete] = useState<Field | null>(null);

  const columns: Column<Field>[] = [
    {
      key: 'field_id',
      header: 'Field ID',
      mono: true,
      cell: (field) => (
        <span className="flex items-center gap-2">
          {field.field_id}
          {field.id === selectedFieldId && (
            <Badge size="sm" tone="info">
              Selected
            </Badge>
          )}
        </span>
      ),
    },
    {
      key: 'area_acre',
      header: 'Area (acres)',
      numeric: true,
      sortable: true,
      cell: (field) => formatDecimal(field.area_acre, 2),
    },
    {
      key: 'vertex_count',
      header: 'Corners',
      numeric: true,
      cell: (field) => field.vertex_count,
    },
    {
      key: 'centroid',
      header: 'Centroid',
      mono: true,
      cell: (field) => formatLatLng(field.centroid_lat, field.centroid_lng),
    },
    {
      key: 'pin',
      header: 'Pin',
      mono: true,
      cell: (field) => formatLatLng(field.pin_lat, field.pin_lng),
    },
    {
      key: 'status',
      header: 'Status',
      cell: () => (
        <Badge size="sm" tone="success">
          Saved
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      cell: (field) => (
        <span className="flex items-center justify-end gap-1">
          <IconButton
            label={`Show the corners of ${field.field_id}`}
            size="sm"
            icon={<List className="h-4 w-4" />}
            onClick={() => onShowVertices(field)}
          />
          <IconButton
            label={`Locate ${field.field_id}`}
            size="sm"
            icon={<Crosshair className="h-4 w-4" />}
            onClick={() => onLocate(field)}
          />
          <IconButton
            label={`Edit the boundary of ${field.field_id}`}
            size="sm"
            icon={<Pencil className="h-4 w-4" />}
            onClick={() => onEdit(field)}
          />
          <IconButton
            label={`Remove ${field.field_id}`}
            size="sm"
            icon={<Trash2 className="h-4 w-4 text-danger" />}
            onClick={() => setPendingDelete(field)}
          />
        </span>
      ),
    },
  ];

  return (
    <>
      <DataTable
        caption="Fields mapped for this farmer, with their areas, corners and coordinates"
        columns={columns}
        rows={fields}
        rowKey={(field) => field.id}
        loading={loading}
        onRowClick={(field) => onSelect(field.id)}
        maxHeight="420px"
        empty={
          <p className="px-4 py-10 text-center text-muted">
            No fields yet. Draw a boundary on the map and save it.
          </p>
        }
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        title={`Remove field ${pendingDelete?.field_id ?? ''}?`}
        description="The field is kept in the record and marked as removed, so its history stays readable. Its field ID is never reused."
        confirmLabel="Remove field"
        destructive
        loading={deleting}
        onConfirm={() => {
          if (pendingDelete) onDelete(pendingDelete);
          setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  );
}
