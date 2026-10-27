import { formatNumber, roleLabel } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { DataTable, type Column } from '@/design-system/components/DataTable';
import { EmptyState } from '@/design-system/components/EmptyState';
import type { OfficerOverview, OfficerRow } from '../api/types';
import { SectionCard } from './SectionCard';

export interface OfficerTableProps {
  data: OfficerOverview | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
}

/**
 * What each officer has registered and submitted this season. Administrators only:
 * the server refuses this section for an officer, and the page does not ask for it.
 */
export function OfficerTable({ data, loading, error, onRetry }: OfficerTableProps) {
  const unit = data?.area_unit ?? 'acre';
  const columns: Column<OfficerRow>[] = [
    {
      key: 'full_name',
      header: 'Officer',
      cell: (row) => (
        <span className="flex flex-col">
          <span className="font-medium text-ink">{row.full_name}</span>
          <span className="mono-id text-xs text-muted">{row.code}</span>
        </span>
      ),
    },
    {
      key: 'field_office_name',
      header: 'Field office',
      cell: (row) => row.field_office_name ?? '-',
    },
    {
      key: 'role',
      header: 'Role',
      cell: (row) => (
        <Badge tone={row.role === 'admin' ? 'info' : 'neutral'} size="sm">
          {roleLabel(row.role)}
        </Badge>
      ),
    },
    { key: 'farmers', header: 'Farmers', numeric: true, cell: (row) => formatNumber(row.farmers) },
    { key: 'fields', header: 'Fields', numeric: true, cell: (row) => formatNumber(row.fields) },
    {
      key: 'area',
      header: `Area (${unit})`,
      numeric: true,
      cell: (row) => formatNumber(row.area, 2),
    },
    {
      key: 'fieldbooks_submitted',
      header: 'Fieldbooks submitted',
      numeric: true,
      cell: (row) => formatNumber(row.fieldbooks_submitted),
    },
  ];

  return (
    <SectionCard
      id="officers-heading"
      title="Officers this season"
      description="Registrations and submitted fieldbooks per officer."
      loading={loading && !data}
      error={error}
      onRetry={onRetry}
      skeletonHeight="h-64"
    >
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(row) => row.officer_id}
        caption="Officers with what each has registered and submitted this season"
        empty={
          <EmptyState
            compact
            title="No officers to show"
            description="Officers are seeded with the reference data."
          />
        }
      />
    </SectionCard>
  );
}
