import { Plus } from 'lucide-react';
import { toApiError } from '@/core/api/errors';
import { Button, Select, toast } from '@/design-system/components';
import type { Crop } from '../api/types';
import { useOpenHeap } from '../hooks/useHeapActions';
import { useHeaps } from '../hooks/useHeaps';
import { words } from '../lib/wording';

export interface HeapPickerProps {
  siteId: string;
  crop: Crop;
  value: string | null;
  onChange: (heapId: string | null) => void;
  disabled?: boolean;
  /** Offer an Open new heap (or batch) shortcut. */
  allowOpenNew?: boolean;
  id?: string;
}

/** Choose one of the open heaps (batches for hemp) at a site, or open a new one. */
export function HeapPicker({ siteId, crop, value, onChange, disabled, allowOpenNew = true, id }: HeapPickerProps) {
  const w = words(crop);
  const heaps = useHeaps({ site_id: siteId, status: 'open' }, Boolean(siteId));
  const open = useOpenHeap();
  const options = (heaps.data ?? []).map((h) => ({
    value: h.id,
    label: `${h.heap_id} (${h.deliveries} ${h.deliveries === 1 ? 'delivery' : 'deliveries'})`,
  }));
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="min-w-[220px] flex-1">
        <Select
          id={id}
          aria-label={`Open ${w.lotLower}`}
          value={value ?? ''}
          disabled={disabled || heaps.isLoading}
          placeholder={heaps.isLoading ? 'Loading' : options.length ? `Choose an open ${w.lotLower}` : `No open ${w.lotLower} at this ${w.siteLower}`}
          options={options}
          onChange={(e) => onChange(e.target.value || null)}
        />
      </div>
      {allowOpenNew && (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          leftIcon={<Plus className="h-4 w-4" />}
          disabled={disabled || !siteId}
          loading={open.isPending}
          onClick={() =>
            open.mutate(
              { siteId },
              {
                onSuccess: (r) => {
                  onChange(r.heap.id);
                  toast.success(`${r.heap.heap_id} opened`, r.warnings[0]);
                },
                onError: (e) => toast.error(`The ${w.lotLower} was not opened`, toApiError(e).message),
              },
            )
          }
        >
          Open new {w.lotLower}
        </Button>
      )}
    </div>
  );
}
