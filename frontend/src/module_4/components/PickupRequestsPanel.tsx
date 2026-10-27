import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { formatDate, formatDateTime, formatNumber } from '@/core/utils/format';
import { Badge, Button, DataTable, Dialog, EmptyState, FormField, Select, Textarea, toast, type Column } from '@/design-system/components';
import { radarApi, radarKeys } from '../api/client';
import type { Crop, PickupRequest, RequestStatus } from '../api/types';
import { useCancelPickup } from '../hooks/useRequestPickup';

const STATUS: Record<RequestStatus, { label: string; tone: 'warning' | 'info' | 'success' | 'neutral' }> = {
  requested: { label: 'Requested', tone: 'warning' },
  scheduled: { label: 'Scheduled', tone: 'info' },
  fulfilled: { label: 'Delivered', tone: 'success' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
};

export interface CancelTarget {
  id: string;
  request_no: string;
  field_code: string;
}

/** Cancel one waiting request. A reason is required. */
export function CancelRequestDialog({ target, onClose }: { target: CancelTarget | null; onClose: () => void }) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const cancel = useCancelPickup();
  useEffect(() => {
    setReason('');
    setError(null);
  }, [target]);
  return (
    <Dialog
      open={target !== null}
      onClose={onClose}
      role="alertdialog"
      size="sm"
      title={`Cancel ${target?.request_no ?? 'request'}?`}
      description={target ? `The pickup for field ${target.field_code} will no longer be collected.` : undefined}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Keep request
          </Button>
          <Button
            variant="danger"
            loading={cancel.isPending}
            onClick={() => {
              if (!reason.trim()) {
                setError('Give a reason for cancelling.');
                return;
              }
              if (!target) return;
              cancel.mutate(
                { id: target.id, reason: reason.trim() },
                {
                  onSuccess: (r) => {
                    toast.success(`${r.request_no} cancelled`);
                    onClose();
                  },
                  onError: (e) => setError(toApiError(e).message),
                },
              );
            }}
          >
            Cancel request
          </Button>
        </>
      }
    >
      <FormField label="Reason" required error={error}>
        <Textarea value={reason} rows={3} maxLength={500} onChange={(e) => setReason(e.target.value)} />
      </FormField>
    </Dialog>
  );
}

/** Pickup requests for the crop and season, with cancelling while still waiting. */
export function PickupRequestsPanel({ crop, season, scope }: { crop: Crop; season: number; scope: 'mine' | 'all' }) {
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<CancelTarget | null>(null);
  const params = { crop, season_year: season, status: status || undefined, scope, page };
  const query = useQuery({
    queryKey: radarKeys.requests(params),
    queryFn: ({ signal }) => radarApi.requests(params, signal),
  });

  const columns: Column<PickupRequest>[] = [
    { key: 'request_no', header: 'Request', mono: true, cell: (r) => r.request_no },
    { key: 'status', header: 'Status', cell: (r) => <Badge tone={STATUS[r.status].tone} size="sm">{STATUS[r.status].label}</Badge> },
    { key: 'field', header: 'Field', mono: true, cell: (r) => r.field_code },
    { key: 'farmer', header: 'Farmer', cell: (r) => (r.farmer_name ? `${r.sawie_id}, ${r.farmer_name}` : '-') },
    {
      key: 'quantity',
      header: 'Estimated quantity',
      numeric: true,
      cell: (r) => (r.estimated_quantity_kg === null ? '-' : `${r.quantity_is_estimate ? 'About ' : ''}${formatNumber(r.estimated_quantity_kg)} kg`),
    },
    { key: 'preferred', header: 'Preferred date', cell: (r) => (r.preferred_date ? formatDate(r.preferred_date) : '-') },
    { key: 'requested', header: 'Requested', cell: (r) => `${formatDateTime(r.requested_at)}${r.requested_by_name ? `, ${r.requested_by_name}` : ''}` },
    {
      key: 'detail',
      header: 'Detail',
      cell: (r) =>
        r.status === 'cancelled'
          ? r.cancel_reason
          : r.delivery_id
            ? `Delivery ${r.delivery_id.slice(0, 8)}`
            : (r.note ?? '-'),
    },
    {
      key: 'actions',
      header: 'Actions',
      cell: (r) =>
        r.can_cancel ? (
          <Button size="sm" variant="ghost" onClick={() => setTarget({ id: r.id, request_no: r.request_no, field_code: r.field_code })}>
            Cancel
          </Button>
        ) : null,
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="max-w-xs">
        <FormField label="Request status">
          <Select
            value={status}
            placeholder="All requests"
            options={Object.entries(STATUS).map(([value, s]) => ({ value, label: s.label }))}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          />
        </FormField>
      </div>
      <DataTable
        caption="Pickup requests"
        columns={columns}
        rows={query.data?.items ?? []}
        rowKey={(r) => r.id}
        loading={query.isLoading}
        pagination={{ page, pageSize: 50, total: query.data?.total ?? 0, onPageChange: setPage }}
        empty={<EmptyState compact title="No pickup requests" description="Select ready fields on the table and request a pickup." />}
      />
      <CancelRequestDialog target={target} onClose={() => setTarget(null)} />
    </div>
  );
}
