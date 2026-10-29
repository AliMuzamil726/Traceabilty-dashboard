import { Truck } from 'lucide-react';
import { toApiError } from '@/core/api/errors';
import { formatDateTime } from '@/core/utils/format';
import { Button, DataTable, EmptyState, ErrorState, toast, type Column } from '@/design-system/components';
import type { Crop, InboundLoad } from '../api/types';
import { useGateActions, useInbound } from '../hooks/useGate';
import { referenceText } from '../lib/gate';

/** Loads on the road to this site with no gate entry yet: record the arrival when they pull in. */
export function InboundSection({ siteId, crop }: { siteId: string; crop: Crop }) {
  const inbound = useInbound({ siteId, crop });
  const { arrive } = useGateActions();
  const rows = inbound.data ?? [];

  const record = (load: InboundLoad) =>
    arrive.mutate(load.delivery_id, {
      onSuccess: () =>
        toast.success(`${load.delivery_no} logged at the gate`, 'Weigh the load, then accept or reject it.'),
      onError: (e) => toast.error('Arrival not recorded', toApiError(e).message),
    });

  const columns: Column<InboundLoad>[] = [
    { key: 'delivery', header: 'Delivery', mono: true, cell: (row) => row.delivery_no },
    {
      key: 'farmer',
      header: 'Farmer',
      cell: (row) => (
        <span className="flex flex-col">
          <span className="font-medium text-ink">{row.farmer_name ?? '-'}</span>
          <span className="text-xs text-muted">
            {row.sawie_id ? `SAWIE ${row.sawie_id}` : 'No SAWIE id'} · {row.field_code}
          </span>
        </span>
      ),
    },
    { key: 'dispatched', header: 'Dispatched', nowrap: true, cell: (row) => formatDateTime(row.dispatched_at) },
    { key: 'reference', header: 'Reference', numeric: true, cell: (row) => referenceText(row) },
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
    {
      key: 'action',
      header: '',
      align: 'right',
      cell: (row) => (
        <Button
          size="sm"
          variant="secondary"
          loading={arrive.isPending && arrive.variables === row.delivery_id}
          onClick={() => record(row)}
        >
          Record arrival
        </Button>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(row) => row.delivery_id}
      caption="Loads in transit that have not reached the gate"
      loading={inbound.isLoading}
      empty={
        inbound.isError ? (
          <ErrorState
            compact
            title="Loads on the road could not be loaded"
            description={toApiError(inbound.error).message}
            onRetry={() => void inbound.refetch()}
          />
        ) : (
          <EmptyState
            compact
            icon={<Truck />}
            title="Nothing on the road"
            description="When a load is dispatched to this site it appears here until its arrival is recorded."
          />
        )
      }
    />
  );
}
