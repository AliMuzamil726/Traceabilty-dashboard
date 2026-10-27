import { Plus } from 'lucide-react';
import { useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { formatDateTime } from '@/core/utils/format';
import { Badge, Button, DataTable, Dialog, EmptyState, FormField, Textarea, toast, type Column } from '@/design-system/components';
import type { Bale, HeapDetail } from '../api/types';
import { useHeapActions } from '../hooks/useHeapActions';
import { RecordBalesDialog } from './RecordBalesDialog';

export function BalesPanel({ heap }: { heap: HeapDetail }) {
  const [recording, setRecording] = useState(false);
  const [target, setTarget] = useState<Bale | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { voidBale } = useHeapActions(heap.id);
  const columns: Column<Bale>[] = [
    { key: 'serial', header: 'Serial', mono: true, cell: (b) => b.bale_serial },
    { key: 'weight', header: 'Weight', numeric: true, cell: (b) => `${b.weight_kg} kg` },
    { key: 'created', header: 'Created', cell: (b) => formatDateTime(b.created_at) },
    { key: 'status', header: 'Status', cell: (b) => (b.status === 'active' ? <Badge tone="success" size="sm">Active</Badge> : <Badge size="sm">Voided: {b.void_reason}</Badge>) },
    {
      key: 'void', header: 'Actions',
      cell: (b) => heap.permissions.can_void_bales && b.status === 'active'
        ? <Button size="sm" variant="ghost" onClick={() => { setTarget(b); setReason(''); setError(null); }}>Void</Button> : null,
    },
  ];
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">{heap.totals.bales_made} of {heap.totals.max_bales} bales made.</p>
        <Button size="sm" leftIcon={<Plus className="h-4 w-4" />} disabled={!heap.permissions.can_record_bales} onClick={() => setRecording(true)}>
          Record bales
        </Button>
      </div>
      <DataTable caption={`Bales of ${heap.heap_id}`} columns={columns} rows={heap.bales} rowKey={(b) => b.id}
        empty={<EmptyState compact title="No bales yet" />} />
      <RecordBalesDialog heap={heap} open={recording} onClose={() => setRecording(false)} />
      <Dialog open={target !== null} onClose={() => setTarget(null)} role="alertdialog" size="sm" title={`Void ${target?.bale_serial ?? ''}?`}
        description="The serial is kept and never reused. The bale no longer counts towards the output."
        footer={<>
          <Button variant="secondary" onClick={() => setTarget(null)}>Keep</Button>
          <Button variant="danger" loading={voidBale.isPending} onClick={() => {
            if (!reason.trim()) { setError('Give a reason.'); return; }
            if (!target) return;
            voidBale.mutate({ serial: target.bale_serial, reason: reason.trim() }, {
              onSuccess: () => { toast.success(`${target.bale_serial} voided`); setTarget(null); },
              onError: (e) => setError(toApiError(e).message),
            });
          }}>Void bale</Button>
        </>}>
        <FormField label="Reason" required error={error}>
          <Textarea rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
        </FormField>
      </Dialog>
    </div>
  );
}
