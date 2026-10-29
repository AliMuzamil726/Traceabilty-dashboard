import { Check, Scale } from 'lucide-react';
import { useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { formatDateTime } from '@/core/utils/format';
import { Button, DataTable, EmptyState, ErrorState, type Column } from '@/design-system/components';
import type { Crop, GateEntry } from '../api/types';
import { useGateEntries } from '../hooks/useGate';
import { referenceText } from '../lib/gate';
import { AcceptDialog } from './AcceptDialog';
import { RejectDialog } from './RejectDialog';

/** Loads standing at the gate: weigh and accept, or refuse with a reason. */
export function PendingSection({ siteId, crop }: { siteId: string; crop: Crop }) {
  const entries = useGateEntries({ siteId, crop, status: 'pending', limit: 100 });
  const [accepting, setAccepting] = useState<GateEntry | null>(null);
  const [rejecting, setRejecting] = useState<GateEntry | null>(null);
  const rows = entries.data?.items ?? [];

  const columns: Column<GateEntry>[] = [
    { key: 'arrived', header: 'Arrived', nowrap: true, cell: (row) => formatDateTime(row.arrived_at) },
    { key: 'delivery', header: 'Delivery', mono: true, cell: (row) => row.delivery_no },
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
    { key: 'reference', header: 'Reference', numeric: true, cell: (row) => referenceText(row) },
    {
      key: 'action',
      header: '',
      align: 'right',
      cell: (row) => (
        <span className="flex justify-end gap-2">
          {row.can_reject && (
            <Button size="sm" variant="secondary" onClick={() => setRejecting(row)}>
              Reject
            </Button>
          )}
          {row.can_accept && (
            <Button size="sm" leftIcon={<Check className="h-4 w-4" />} onClick={() => setAccepting(row)}>
              Accept
            </Button>
          )}
        </span>
      ),
    },
  ];

  return (
    <>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption="Loads waiting at the gate"
        loading={entries.isLoading}
        empty={
          entries.isError ? (
            <ErrorState
              compact
              title="The gate queue could not be loaded"
              description={toApiError(entries.error).message}
              onRetry={() => void entries.refetch()}
            />
          ) : (
            <EmptyState
              compact
              icon={<Scale />}
              title="The gate is clear"
              description="Record an arrival above and the load waits here until it is weighed and decided."
            />
          )
        }
      />
      {accepting && <AcceptDialog entry={accepting} open onClose={() => setAccepting(null)} />}
      {rejecting && <RejectDialog entry={rejecting} open onClose={() => setRejecting(null)} />}
    </>
  );
}
