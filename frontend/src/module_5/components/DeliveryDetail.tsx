import { Ban, PackageCheck, Pencil, Send, Wrench } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { formatDate, formatDateTime } from '@/core/utils/format';
import { Button, Card, Dialog, EmptyState, FormField, KeyValueList, NumberInput, SectionHeader, Skeleton, Textarea, toast } from '@/design-system/components';
import { HeapPicker, useAssignToHeap } from '@/module_6';
import type { DeliveryDetail as Detail } from '../api/types';
import { useDelivery } from '../hooks/useDeliveries';
import { useTransition } from '../hooks/useTransition';
import { actionsFor } from '../lib/status';
import { siteWord } from '../lib/variance';
import { CancelDialog } from './CancelDialog';
import { StatusPill } from './DeliveryList';
import { DispatchDialog } from './DispatchDialog';
import { ReceiveDialog } from './ReceiveDialog';
import { ScheduleDialog } from './ScheduleDialog';
import { SlipButton } from './SlipButton';
import { StatusTimeline } from './StatusTimeline';
import { WeightBlock } from './WeightBlock';

type Open = 'edit' | 'dispatch' | 'receive' | 'cancel' | 'correct' | null;

function CorrectDialog({ d, open, onClose }: { d: Detail; open: boolean; onClose: () => void }) {
  const [weight, setWeight] = useState<number | null>(null);
  const [moisture, setMoisture] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { correct } = useTransition(d.id);
  useEffect(() => { if (open) { setWeight(d.weighbridge_weight_kg); setMoisture(d.moisture_pct); setReason(''); setError(null); } }, [open, d]);
  return (
    <Dialog open={open} onClose={onClose} title={`Correct ${d.delivery_no}`} description="Administrator correction of a delivered record. The change and its reason are audited."
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button loading={correct.isPending} onClick={() => {
          if (!reason.trim()) { setError('A correction needs a reason.'); return; }
          correct.mutate({ reason: reason.trim(), weighbridge_weight_kg: weight, moisture_pct: moisture }, {
            onSuccess: () => { toast.success(`${d.delivery_no} corrected`); onClose(); },
            onError: (e) => setError(toApiError(e).message),
          });
        }}>Save correction</Button>
      </>}>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Weighbridge weight"><NumberInput value={weight} onValueChange={setWeight} unit="kg" min={0} /></FormField>
        <FormField label="Moisture"><NumberInput value={moisture} onValueChange={setMoisture} unit="%" min={0} max={100} decimals={1} /></FormField>
        <FormField label="Reason" required error={error} className="col-span-2">
          <Textarea rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
        </FormField>
      </div>
    </Dialog>
  );
}

function HeapBlock({ d }: { d: Detail }) {
  const word = siteWord(d.crop);
  const [heapId, setHeapId] = useState<string | null>(null);
  const assign = useAssignToHeap();
  if (d.heap_id) return <p className="font-mono text-sm text-ink">{d.heap_id}</p>;
  if (d.status !== 'delivered') return <p className="text-sm text-muted">Pending, after delivery</p>;
  if (!d.site) return <p className="text-sm text-muted">Pending</p>;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted">Pending: not in a {word.lot.toLowerCase()} yet.</p>
      <HeapPicker siteId={d.site.id} crop={d.crop} value={heapId} onChange={setHeapId} disabled={!d.can_act} />
      <Button size="sm" className="self-start" disabled={!heapId || !d.can_act} loading={assign.isPending}
        onClick={() => heapId && assign.mutate({ heapId, deliveryId: d.id }, {
          onSuccess: (heap) => toast.success(`Added to ${heap.heap_id}`),
          onError: (e) => toast.error(`Not added to the ${word.lot.toLowerCase()}`, toApiError(e).message),
        })}>
        Assign to {word.lot.toLowerCase()}
      </Button>
    </div>
  );
}

export function DeliveryDetail({ id, isAdmin }: { id: string | null; isAdmin: boolean }) {
  const query = useDelivery(id);
  const [open, setOpen] = useState<Open>(null);
  if (!id) return <EmptyState title="Choose a delivery" description="Select a delivery on the left to see its details." />;
  if (query.error) return <EmptyState title="This delivery cannot be opened" description={toApiError(query.error).message} />;
  const d = query.data;
  if (!d) return <Skeleton className="h-96 w-full" shape="block" />;
  const can = actionsFor(d.status, d.can_act, isAdmin);
  const word = siteWord(d.crop);
  return (
    <Card padding="lg" as="section" aria-labelledby="delivery-title" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="delivery-title" className="font-mono text-xl font-semibold text-ink">{d.delivery_no}</h2>
          <p className="text-sm text-muted">{d.crop === 'cotton' ? 'Cotton' : 'Hemp'}, season {d.season_year}{d.can_act ? '' : ', read only'}</p>
        </div>
        <StatusPill status={d.status} />
      </div>
      <div className="flex flex-wrap gap-2" aria-label="Actions">
        {can.edit && <Button size="sm" variant="secondary" leftIcon={<Pencil className="h-4 w-4" />} onClick={() => setOpen('edit')}>Edit schedule</Button>}
        {can.dispatch && <Button size="sm" leftIcon={<Send className="h-4 w-4" />} onClick={() => setOpen('dispatch')}>Dispatch</Button>}
        {can.receive && <Button size="sm" leftIcon={<PackageCheck className="h-4 w-4" />} onClick={() => setOpen('receive')}>Receive at gate</Button>}
        {can.cancel && <Button size="sm" variant="ghost" leftIcon={<Ban className="h-4 w-4" />} onClick={() => setOpen('cancel')}>Cancel</Button>}
        {can.correct && <Button size="sm" variant="secondary" leftIcon={<Wrench className="h-4 w-4" />} onClick={() => setOpen('correct')}>Correct</Button>}
        <SlipButton deliveryId={d.id} />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section aria-labelledby="farmer-h">
          <SectionHeader as="h3" id="farmer-h" title="Farmer and field" />
          <KeyValueList className="mt-2" items={[
            { label: 'Farmer', value: d.farmer_name ? `${d.farmer_name} (SAWIE ${d.sawie_id})` : '-' },
            { label: d.crop === 'cotton' ? 'Father' : 'Farm', value: d.father_or_farm ?? '-' },
            { label: 'Field', value: d.field_code, mono: true },
            { label: 'Location', value: d.location },
            { label: 'Officer', value: d.officer_name ?? '-' },
          ]} />
        </section>
        <section aria-labelledby="transport-h">
          <SectionHeader as="h3" id="transport-h" title="Transport" />
          <KeyValueList className="mt-2" items={[
            { label: word.site, value: d.site ? `${d.site.name} (${d.site.code})` : '-' },
            { label: 'Scheduled date', value: formatDate(d.scheduled_date) },
            { label: 'Driver', value: `${d.driver_name}, ${d.driver_phone}` },
            { label: 'Vehicle', value: d.vehicle_no, mono: true },
            { label: 'Dispatched', value: d.dispatched_at ? formatDateTime(d.dispatched_at) : '-' },
            { label: 'Delivered', value: d.delivered_at ? formatDateTime(d.delivered_at) : '-' },
          ]} />
        </section>
        <section aria-labelledby="weights-h">
          <SectionHeader as="h3" id="weights-h" title="Weights" />
          <div className="mt-2"><WeightBlock d={d} /></div>
        </section>
        <section aria-labelledby="heap-h">
          <SectionHeader as="h3" id="heap-h" title={word.lot} />
          <div className="mt-2"><HeapBlock d={d} /></div>
        </section>
        <section aria-labelledby="history-h">
          <SectionHeader as="h3" id="history-h" title="Status timeline" />
          <div className="mt-3"><StatusTimeline history={d.history} /></div>
        </section>
        <section aria-labelledby="notes-h">
          <SectionHeader as="h3" id="notes-h" title="Notes" />
          <p className="mt-2 whitespace-pre-line text-sm text-ink">{d.note ?? 'No notes.'}</p>
          {d.cancel_reason && <p className="mt-2 text-sm text-muted">Cancelled: {d.cancel_reason}</p>}
        </section>
      </div>

      <ScheduleDialog open={open === 'edit'} delivery={d} onClose={() => setOpen(null)} />
      <DispatchDialog delivery={d} open={open === 'dispatch'} onClose={() => setOpen(null)} />
      <ReceiveDialog delivery={d} open={open === 'receive'} onClose={() => setOpen(null)} />
      <CancelDialog delivery={d} open={open === 'cancel'} onClose={() => setOpen(null)} />
      <CorrectDialog d={d} open={open === 'correct'} onClose={() => setOpen(null)} />
    </Card>
  );
}
