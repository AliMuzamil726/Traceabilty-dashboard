import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { Button, Dialog, FormField, Textarea, toast } from '@/design-system/components';
import type { GateEntry } from '../api/types';
import { useGateActions } from '../hooks/useGate';
import { validateReject } from '../lib/gate';

/** Refusing a load cancels its delivery; the reason is kept on both records. */
export function RejectDialog({ entry, open, onClose }: { entry: GateEntry; open: boolean; onClose: () => void }) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { reject } = useGateActions();
  useEffect(() => {
    if (!open) return;
    setReason('');
    setError(null);
  }, [open, entry.id]);

  const confirm = () => {
    const found = validateReject(reason);
    setError(found);
    if (found) return;
    reject.mutate(
      { entryId: entry.id, reason: reason.trim() },
      {
        onSuccess: () => {
          toast.success(`${entry.delivery_no} rejected`, 'The delivery was cancelled with this reason.');
          onClose();
        },
        onError: (e) => setError(toApiError(e).message),
      },
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Reject ${entry.delivery_no}`}
      description={`Rejecting cancels this delivery. ${entry.vehicle_no} · ${entry.driver_name}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" loading={reject.isPending} onClick={confirm}>Reject load</Button>
        </>
      }
    >
      <FormField label="Reason" required error={error} hint="Kept on the gate entry and the delivery's history.">
        <Textarea
          rows={3}
          maxLength={500}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Wrong vehicle for this load, refused by the ginner, spoiled crop..."
        />
      </FormField>
    </Dialog>
  );
}
