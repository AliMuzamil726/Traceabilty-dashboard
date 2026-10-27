import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { Button, Dialog, FormField, Textarea, toast } from '@/design-system/components';
import type { DeliveryDetail } from '../api/types';
import { useTransition } from '../hooks/useTransition';

export function CancelDialog({ delivery, open, onClose }: { delivery: DeliveryDetail; open: boolean; onClose: () => void }) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { cancel } = useTransition(delivery.id);
  useEffect(() => { if (open) { setReason(''); setError(null); } }, [open]);
  return (
    <Dialog open={open} onClose={onClose} role="alertdialog" size="sm" title={`Cancel ${delivery.delivery_no}?`}
      description="The pickup request in Harvest Radar is closed too, so the field can be requested again."
      footer={<>
        <Button variant="secondary" onClick={onClose}>Keep delivery</Button>
        <Button variant="danger" loading={cancel.isPending} onClick={() => {
          if (!reason.trim()) { setError('Give a reason for cancelling.'); return; }
          cancel.mutate(reason.trim(), {
            onSuccess: () => { toast.success(`${delivery.delivery_no} cancelled`); onClose(); },
            onError: (e) => setError(toApiError(e).message),
          });
        }}>Cancel delivery</Button>
      </>}>
      <FormField label="Reason" required error={error}>
        <Textarea rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
      </FormField>
    </Dialog>
  );
}
