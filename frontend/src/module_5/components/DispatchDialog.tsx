import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { Button, Dialog, FormField, NumberInput, Textarea, toast } from '@/design-system/components';
import type { DeliveryDetail } from '../api/types';
import { useTransition } from '../hooks/useTransition';
import { maunds } from '../lib/variance';

export function DispatchDialog({ delivery, open, onClose }: { delivery: DeliveryDetail; open: boolean; onClose: () => void }) {
  const [weight, setWeight] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { dispatch } = useTransition(delivery.id);
  useEffect(() => { if (open) { setWeight(null); setNote(''); setError(null); } }, [open]);
  return (
    <Dialog open={open} onClose={onClose} title={`Dispatch ${delivery.delivery_no}`} description="The lorry is leaving the farm."
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button loading={dispatch.isPending} onClick={() => {
          if (weight !== null && weight <= 0) { setError('Enter a weight above 0 kg, or leave it empty.'); return; }
          dispatch.mutate({ field_weight_kg: weight, note: note.trim() || null }, {
            onSuccess: () => { toast.success(`${delivery.delivery_no} dispatched`); onClose(); },
            onError: (e) => setError(toApiError(e).message),
          });
        }}>Dispatch</Button>
      </>}>
      <div className="flex flex-col gap-4">
        <FormField label="Field weight" hint={weight && delivery.crop === 'cotton' ? `${maunds(weight)} maunds. Optional.` : 'Optional, if weighed at the farm.'} error={error}>
          <NumberInput value={weight} onValueChange={setWeight} unit="kg" min={0} />
        </FormField>
        <FormField label="Note" hint="Optional.">
          <Textarea rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
        </FormField>
      </div>
    </Dialog>
  );
}
