import { ClipboardList } from 'lucide-react';
import { useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { cn } from '@/core/utils/cn';
import { formatDateTime, formatNumber } from '@/core/utils/format';
import {
  DataTable,
  EmptyState,
  ErrorState,
  SectionHeader,
  SegmentedControl,
  StatusPill,
  type Column,
  type Tone,
} from '@/design-system/components';
import type { Crop, GateEntry, GateStatus } from '../api/types';
import { useGateEntries } from '../hooks/useGate';
import { kgText, STATUS_LABEL } from '../lib/gate';

type HistoryFilter = 'decided' | 'accepted' | 'rejected';

const TONE: Record<GateStatus, Tone> = { pending: 'warning', accepted: 'success', rejected: 'danger' };

/** The gate's record: every decided load, newest first, filterable by outcome. */
export function HistorySection({ siteId, crop }: { siteId: string; crop: Crop }) {
  const [filter, setFilter] = useState<HistoryFilter>('decided');
  const entries = useGateEntries({
    siteId,
    crop,
    status: filter,
    limit: 50,
  });
  const rows = entries.data?.items ?? [];
  const total = entries.data?.total ?? 0;

  const columns: Column<GateEntry>[] = [
    {
      key: 'delivery',
      header: 'Delivery',
      cell: (row) => (
        <span className="flex flex-col gap-1">
          <span className="mono-id text-sm">{row.delivery_no}</span>
          <StatusPill tone={TONE[row.status]} size="sm">{STATUS_LABEL[row.status]}</StatusPill>
        </span>
      ),
    },
    {
      key: 'vehicle',
      header: 'Vehicle',
      cell: (row) => (
        <span className="flex flex-col">
          <span className="font-mono text-sm">{row.vehicle_no}</span>
          <span className="text-xs text-muted">{row.driver_name}</span>
        </span>
      ),
    },
    { key: 'net', header: 'Net', numeric: true, cell: (row) => kgText(row.net_weight_kg, row.crop) },
    {
      key: 'moisture',
      header: 'Moisture',
      numeric: true,
      cell: (row) => (row.moisture_pct === null ? '-' : `${row.moisture_pct}%`),
    },
    {
      key: 'decided',
      header: 'Decided',
      nowrap: true,
      cell: (row) => formatDateTime(row.accepted_at ?? row.rejected_at),
    },
    {
      key: 'detail',
      header: 'Note or reason',
      cell: (row) => (
        <span className={cn('text-sm', row.rejection_reason ? 'text-danger' : 'text-muted')}>
          {row.rejection_reason ?? row.note ?? '-'}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <SectionHeader
        as="h2"
        id="gate-history-h"
        title="Recent entries"
        actions={
          <SegmentedControl
            size="sm"
            aria-label="Entry status"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'decided', label: 'All' },
              { value: 'accepted', label: 'Accepted' },
              { value: 'rejected', label: 'Rejected' },
            ]}
          />
        }
      />
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption="Decided gate entries"
        loading={entries.isLoading}
        empty={
          entries.isError ? (
            <ErrorState
              compact
              title="Recent entries could not be loaded"
              description={toApiError(entries.error).message}
              onRetry={() => void entries.refetch()}
            />
          ) : (
            <EmptyState
              compact
              icon={<ClipboardList />}
              title="No decided loads yet"
              description={
                filter === 'decided'
                  ? 'Accepted and rejected loads appear here with their weights.'
                  : `No ${filter} loads yet at this site.`
              }
            />
          )
        }
      />
      {total > rows.length && (
        <p className="text-sm text-muted">
          Showing the latest {formatNumber(rows.length)} of {formatNumber(total)} entries.
        </p>
      )}
    </div>
  );
}
