import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { Button, Dialog, FormField, NumberInput, toast } from '@/design-system/components';
import type { HeapDetail } from '../api/types';
import { useHeapActions } from '../hooks/useHeapActions';
import { validateBaleCount } from '../lib/rules';

export function RecordBalesDialog({ heap, open, onClose }: { heap: HeapDetail; open: boolean; onClose: () => void }) {
  const canAdd = heap.totals.can_add_bales;
  const [count, setCount] = useState<number | null>(1);
  const [error, setError] = useState<string | null>(null);
  const { createBales } = useHeapActions(heap.id);
  useEffect(() => { if (open) { setCount(Math.min(1, canAdd)); setError(null); } }, [open, canAdd]);
  const next = heap.bales.length + 1;
  return (
    <Dialog open={open} onClose={onClose} title="Record bales" description={`Each bale is ${Number(heap.totals.bale_unit_kg)} kg. Serials continue from ${heap.heap_id}-${String(next).padStart(3, '0')}.`}
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button loading={createBales.isPending} onClick={() => {
          const problem = validateBaleCount(count, canAdd);
          setError(problem);
          if (problem || count === null) return;
          createBales.mutate(count, {
            onSuccess: () => { toast.success(`${count} ${count === 1 ? 'bale' : 'bales'} recorded`); onClose(); },
            onError: (e) => setError(toApiError(e).message),
          });
        }}>Record</Button>
      </>}>
      <FormField label="Number of bales" required error={error} hint={`${canAdd} more ${canAdd === 1 ? 'fits' : 'fit'} the expected output.`}>
        <NumberInput value={count} onValueChange={setCount} min={1} max={canAdd} decimals={0} />
      </FormField>
    </Dialog>
  );
}
