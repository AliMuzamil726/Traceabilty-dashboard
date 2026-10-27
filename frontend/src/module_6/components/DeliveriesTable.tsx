import { useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { formatDate, formatNumber } from '@/core/utils/format';
import { Button, DataTable, Dialog, EmptyState, FormField, Textarea, toast, type Column } from '@/design-system/components';
import type { HeapDetail, HeapMember } from '../api/types';
import { useHeapActions } from '../hooks/useHeapActions';
import { words } from '../lib/wording';

export function DeliveriesTable({ heap }: { heap: HeapDetail }) {
  const [target, setTarget] = useState<HeapMember | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { removeDelivery } = useHeapActions(heap.id);
  const w = words(heap.crop);
  const columns: Column<HeapMember>[] = [
    { key: 'no', header: 'Delivery', mono: true, cell: (r) => r.delivery_no },
    { key: 'sawie', header: 'SAWIE ID', mono: true, cell: (r) => r.sawie_id ?? '-' },
    { key: 'farmer', header: 'Farmer', cell: (r) => r.farmer_name ?? '-' },
    { key: 'place', header: heap.crop === 'cotton' ? 'Village' : 'Farm', cell: (r) => r.village_or_farm ?? '-' },
    { key: 'date', header: 'Delivered', cell: (r) => (r.delivered_at ? formatDate(r.delivered_at) : '-') },
    { key: 'field_weight', header: 'Field weight (kg)', numeric: true, cell: (r) => formatNumber(r.field_weight_kg, 1) },
    { key: 'weighbridge', header: 'Weighbridge (kg)', numeric: true, cell: (r) => formatNumber(r.weighbridge_weight_kg, 1) },
    { key: 'moisture', header: 'Moisture', numeric: true, cell: (r) => (r.moisture_pct === null ? '-' : `${r.moisture_pct}%`) },
    {
      key: 'remove', header: 'Actions',
      cell: (r) => heap.permissions.can_remove_deliveries ? (
        <Button size="sm" variant="ghost" onClick={() => { setTarget(r); setReason(''); setError(null); }}>Remove</Button>
      ) : null,
    },
  ];
  return (
    <>
      <DataTable caption={`Deliveries in ${heap.heap_id}`} columns={columns} rows={heap.deliveries} rowKey={(r) => r.delivery_id}
        empty={<EmptyState compact title="No deliveries yet" description={`Receive delivered loads into this ${w.lotLower}.`} />} />
      <Dialog open={target !== null} onClose={() => setTarget(null)} role="alertdialog" size="sm" title={`Remove ${target?.delivery_no ?? ''}?`}
        description={`The delivery goes back to pending and can join another ${w.lotLower}.`}
        footer={<>
          <Button variant="secondary" onClick={() => setTarget(null)}>Keep</Button>
          <Button variant="danger" loading={removeDelivery.isPending} onClick={() => {
            if (!reason.trim()) { setError('Give a reason.'); return; }
            if (!target) return;
            removeDelivery.mutate({ id: target.delivery_id, reason: reason.trim() }, {
              onSuccess: () => { toast.success(`${target.delivery_no} removed`); setTarget(null); },
              onError: (e) => setError(toApiError(e).message),
            });
          }}>Remove delivery</Button>
        </>}>
        <FormField label="Reason" required error={error}>
          <Textarea rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
        </FormField>
      </Dialog>
    </>
  );
}
