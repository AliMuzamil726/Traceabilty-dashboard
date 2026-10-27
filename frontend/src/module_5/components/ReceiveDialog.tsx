import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { cn } from '@/core/utils/cn';
import { Button, Dialog, FormField, NumberInput, Textarea, toast } from '@/design-system/components';
import { HeapPicker, useAssignToHeap } from '@/module_6';
import type { DeliveryDetail } from '../api/types';
import { useTransition } from '../hooks/useTransition';
import { LEVEL_CLASSES, LEVEL_LABEL } from '../lib/status';
import { maunds, previewVariance, siteWord } from '../lib/variance';

/** Receive at the gate: weighbridge weight and moisture, with the variance shown before confirming. */
export function ReceiveDialog({ delivery, open, onClose }: { delivery: DeliveryDetail; open: boolean; onClose: () => void }) {
  const [weight, setWeight] = useState<number | null>(null);
  const [moisture, setMoisture] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [heapId, setHeapId] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const { receive } = useTransition(delivery.id);
  const assign = useAssignToHeap();
  useEffect(() => { if (open) { setWeight(null); setMoisture(null); setNote(''); setHeapId(null); setErrors({}); } }, [open]);

  const t = delivery.thresholds;
  const v = previewVariance(weight, delivery.field_weight_kg, delivery.estimated_quantity_kg, t);
  const moistureHigh = moisture !== null && moisture > t.moisture_warn_pct;
  const needsNote = v.level === 'flag';
  const word = siteWord(delivery.crop);

  const confirm = () => {
    const found: Record<string, string> = {};
    if (!weight || weight <= 0) found.weight = 'Enter the weighbridge weight, above 0 kg.';
    if (moisture === null || moisture < 0 || moisture > 100) found.moisture = 'Enter moisture from 0 to 100 percent.';
    if (needsNote && !note.trim()) found.note = `The weight differs by more than ${t.variance_flag_pct}%. Explain why.`;
    setErrors(found);
    if (Object.keys(found).length || weight === null || moisture === null) return;
    receive.mutate(
      { weighbridge_weight_kg: weight, moisture_pct: moisture, note: note.trim() || null },
      {
        onSuccess: (r) => {
          toast.success(`${delivery.delivery_no} delivered`, r.warnings.join(' ') || undefined);
          if (heapId && delivery.site) {
            assign.mutate({ heapId, deliveryId: delivery.id }, {
              onSuccess: (heap) => toast.success(`Added to ${heap.heap_id}`),
              onError: (e) => toast.error(`Not added to the ${word.lot.toLowerCase()}`, toApiError(e).message),
            });
          }
          onClose();
        },
        onError: (e) => {
          const err = toApiError(e);
          setErrors({ form: err.message, ...err.fieldErrors });
        },
      },
    );
  };

  return (
    <Dialog open={open} onClose={onClose} title={`Receive ${delivery.delivery_no} at the gate`} size="lg"
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button loading={receive.isPending} onClick={confirm}>Confirm receipt</Button>
      </>}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormField label="Weighbridge weight" required error={errors.weight ?? errors.weighbridge_weight_kg}
          hint={weight && delivery.crop === 'cotton' ? `${maunds(weight)} maunds` : undefined}>
          <NumberInput value={weight} onValueChange={setWeight} unit="kg" min={0} />
        </FormField>
        <FormField label="Moisture" required error={errors.moisture ?? errors.moisture_pct}
          hint={moistureHigh ? <span className="text-wheat-600">Above the {t.moisture_warn_pct}% limit for {delivery.crop}.</span> : `Limit ${t.moisture_warn_pct}%`}>
          <NumberInput value={moisture} onValueChange={setMoisture} unit="%" min={0} max={100} decimals={1} />
        </FormField>
        <div className="rounded-control border border-line bg-canvas p-3 sm:col-span-2" aria-live="polite" data-testid="variance-preview">
          {v.level === null ? (
            <p className="text-sm text-muted">
              {v.referenceKg ? 'Enter the weighbridge weight to see the variance.' : 'No field weight or estimate to compare with.'}
            </p>
          ) : (
            <p className={cn('text-sm font-medium', LEVEL_CLASSES[v.level])}>
              Variance {v.varianceKg !== null && v.varianceKg > 0 ? '+' : ''}{v.varianceKg} kg ({v.variancePct}%) against the{' '}
              {v.reference === 'field_weight' ? 'field weight' : 'estimate'} of {v.referenceKg?.toLocaleString('en-GB')} kg: {LEVEL_LABEL[v.level]}.
            </p>
          )}
          <p className="mt-1 text-xs text-muted">Check at {t.variance_warn_pct}%, flag at {t.variance_flag_pct}%.</p>
        </div>
        <FormField label="Note" required={needsNote} error={errors.note} className="sm:col-span-2" hint={needsNote ? undefined : 'Optional.'}>
          <Textarea rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
        </FormField>
        {delivery.site && (
          <FormField label={`Assign to ${word.lot.toLowerCase()}`} hint="Optional. You can also do this later." className="sm:col-span-2">
            <HeapPicker siteId={delivery.site.id} crop={delivery.crop} value={heapId} onChange={setHeapId} />
          </FormField>
        )}
        {errors.form && <p role="alert" className="text-sm text-danger sm:col-span-2">{errors.form}</p>}
      </div>
    </Dialog>
  );
}
