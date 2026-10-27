import { Check, Pencil, X } from 'lucide-react';
import { useState } from 'react';
import { formatNumber } from '@/core/utils/format';
import { IconButton, NumberInput, ProgressBar, StatCard } from '@/design-system/components';
import type { HeapDetail } from '../api/types';
import { useHeapActions } from '../hooks/useHeapActions';
import { kgText, words } from '../lib/wording';

/** Input, outturn (editable until the first bale), expected output, bales and what remains. */
export function HeapKpis({ heap }: { heap: HeapDetail }) {
  const t = heap.totals;
  const w = words(heap.crop);
  const [editing, setEditing] = useState(false);
  const [ratio, setRatio] = useState<number | null>(heap.outturn_ratio_pct);
  const { update } = useHeapActions(heap.id);
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        <StatCard label="Input" value={kgText(t.input_kg)} hint={t.input_maunds ? `${formatNumber(Number(t.input_maunds), 2)} maunds of seed cotton` : `${heap.deliveries.length} deliveries`} />
        <StatCard
          label="Outturn"
          value={
            editing ? (
              <span className="flex items-center gap-1">
                <NumberInput aria-label="Outturn percentage" value={ratio} onValueChange={setRatio} unit="%" min={0} max={100} decimals={2} className="w-24" />
                <IconButton label="Save outturn" icon={<Check className="h-4 w-4" />} onClick={() => ratio && update.mutate({ outturn_ratio_pct: ratio }, { onSuccess: () => setEditing(false) })} />
                <IconButton label="Cancel" icon={<X className="h-4 w-4" />} onClick={() => { setRatio(heap.outturn_ratio_pct); setEditing(false); }} />
              </span>
            ) : (
              <span className="flex items-center gap-1">
                {Number(t.outturn_ratio_pct)}%
                {heap.permissions.can_edit_values && <IconButton label="Edit outturn" icon={<Pencil className="h-4 w-4" />} size="sm" onClick={() => setEditing(true)} />}
              </span>
            )
          }
          hint={heap.permissions.can_edit_values ? `Seed to ${w.output}. Fixed once the first bale exists.` : 'Fixed'}
        />
        <StatCard label="Expected output" value={kgText(t.expected_output_kg)} hint={`Bales of ${Number(t.bale_unit_kg)} kg`} />
        <StatCard label="Bales made" value={`${t.bales_made} of ${t.max_bales}`} hint={`${t.can_add_bales} more possible`} />
        <StatCard label="Remaining" value={kgText(t.remaining_output_kg)} hint={`${kgText(t.remaining_input_kg)} of input left`} />
      </div>
      <ProgressBar value={Number(t.consumed_pct)} max={100} label={`Input consumed: ${Number(t.consumed_pct)}%`} showValue />
      {heap.crop === 'hemp' && (
        <p className="text-sm text-muted">
          Expected shiv {kgText(t.expected_shiv_kg)} ({heap.shiv_pct}%), dust {kgText(t.expected_dust_kg)} ({heap.dust_pct}%).
        </p>
      )}
    </div>
  );
}
