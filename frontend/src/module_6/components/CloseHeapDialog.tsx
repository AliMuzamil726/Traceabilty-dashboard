import { Lock } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { Button, Dialog, FormField, Textarea, Tooltip, toast } from '@/design-system/components';
import type { HeapDetail } from '../api/types';
import { useHeapActions } from '../hooks/useHeapActions';
import { closeState } from '../lib/rules';
import { kgText, words } from '../lib/wording';

/** The Close button and its dialog. With a remainder it needs a reason (administrators only). */
export function CloseHeapDialog({ heap }: { heap: HeapDetail }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { close } = useHeapActions(heap.id);
  const w = words(heap.crop);
  const state = closeState(heap);
  const remainder = state.mode === 'remainder';
  const reasonRequired = remainder || heap.totals.bales_made === 0;
  useEffect(() => { if (open) { setReason(''); setError(null); } }, [open]);
  if (heap.status !== 'open') return null;
  return (
    <>
      <Tooltip disabled={!state.hint} content={state.hint}>
        <Button variant={remainder ? 'secondary' : 'primary'} leftIcon={<Lock className="h-4 w-4" />}
          aria-disabled={state.mode === 'none' || undefined}
          className={state.mode === 'none' ? 'cursor-not-allowed opacity-50' : undefined}
          onClick={() => state.mode !== 'none' && setOpen(true)}>
          {remainder ? 'Close with remainder' : `Close ${w.lotLower}`}
        </Button>
      </Tooltip>
      <Dialog open={open} onClose={() => setOpen(false)} role="alertdialog" title={`Close ${heap.heap_id}?`}
        description={`A closed ${w.lotLower} is locked: no deliveries, bales, ratio or unit changes.`}
        footer={<>
          <Button variant="secondary" onClick={() => setOpen(false)}>Keep open</Button>
          <Button loading={close.isPending} onClick={() => {
            if (reasonRequired && !reason.trim()) { setError(remainder ? 'Closing with a remainder needs a reason.' : 'Closing with no bales needs a reason.'); return; }
            close.mutate({ reason: reason.trim() || null, with_remainder: remainder }, {
              onSuccess: () => { toast.success(`${heap.heap_id} closed`); setOpen(false); },
              onError: (e) => setError(toApiError(e).message),
            });
          }}>Close {w.lotLower}</Button>
        </>}>
        <div className="flex flex-col gap-3">
          {remainder && (
            <p className="text-sm text-ink">
              {kgText(heap.totals.remaining_input_kg)} of input ({kgText(heap.totals.remaining_output_kg)} of expected output) is left over. It is recorded in the audit log.
            </p>
          )}
          <FormField label="Reason" required={reasonRequired} error={error} hint={reasonRequired ? undefined : 'Optional.'}>
            <Textarea rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
          </FormField>
        </div>
      </Dialog>
    </>
  );
}
