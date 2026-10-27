import { useEffect, useState } from 'react';
import { formatDate, formatNumber } from '@/core/utils/format';
import { Button, Drawer, EmptyState, toast } from '@/design-system/components';
import type { HeapDetail } from '../api/types';
import { useHeapActions } from '../hooks/useHeapActions';
import { words } from '../lib/wording';

/** Delivered deliveries at this site and crop that are not in any heap yet. */
export function ReceiveDeliveriesDrawer({ heap, open, onClose }: { heap: HeapDetail; open: boolean; onClose: () => void }) {
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const { addDeliveries } = useHeapActions(heap.id);
  const w = words(heap.crop);
  useEffect(() => { if (open) setChosen(new Set()); }, [open]);
  const rows = heap.pending_deliveries;
  const toggle = (id: string) => setChosen((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const kg = rows.filter((r) => chosen.has(r.id)).reduce((sum, r) => sum + (r.weighbridge_weight_kg ?? 0), 0);
  return (
    <Drawer open={open} onClose={onClose} title={`Receive deliveries into ${heap.heap_id}`} width="w-[460px]"
      footer={
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-muted">{chosen.size} selected, {formatNumber(kg)} kg</span>
          <Button disabled={chosen.size === 0} loading={addDeliveries.isPending} onClick={() =>
            addDeliveries.mutate([...chosen], {
              onSuccess: (r) => {
                toast.success(`${r.added.length} added to ${heap.heap_id}`, r.skipped.map((s) => `${s.delivery_no}: ${s.reason}`).join(' ') || undefined);
                onClose();
              },
            })}>
            Add to {w.lotLower}
          </Button>
        </div>
      }>
      {rows.length === 0 ? (
        <EmptyState compact title="Nothing pending" description={`Every delivered load at this ${w.siteLower} is already in a ${w.lotLower}.`} />
      ) : (
        <ul className="flex flex-col gap-1.5" aria-label="Pending deliveries">
          {rows.map((r) => (
            <li key={r.id}>
              <label className="flex cursor-pointer items-start gap-3 rounded-control border border-line p-3 hover:border-forest-500">
                <input type="checkbox" className="mt-1 h-4 w-4 accent-forest-700" checked={chosen.has(r.id)} onChange={() => toggle(r.id)} aria-label={`Select ${r.delivery_no}`} />
                <span className="flex-1">
                  <span className="flex justify-between gap-2"><span className="font-mono text-sm font-semibold">{r.delivery_no}</span><span className="tabular text-sm">{formatNumber(r.weighbridge_weight_kg)} kg</span></span>
                  <span className="block text-sm">{r.farmer_name ?? '-'} <span className="text-muted">{r.village_or_farm ?? ''}</span></span>
                  <span className="block text-xs text-muted">{r.delivered_at ? formatDate(r.delivered_at) : ''}{r.moisture_pct !== null ? `, moisture ${r.moisture_pct}%` : ''}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
    </Drawer>
  );
}
