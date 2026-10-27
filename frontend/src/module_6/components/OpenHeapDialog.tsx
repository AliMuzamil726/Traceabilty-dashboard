import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { useSites } from '@/core/hooks/useSharedData';
import { Button, Dialog, FormField, Select, Textarea, toast } from '@/design-system/components';
import type { Crop } from '../api/types';
import { useOpenHeap } from '../hooks/useHeapActions';
import { useHeaps } from '../hooks/useHeaps';
import { words } from '../lib/wording';

export function OpenHeapDialog({ crop, siteId, open, onClose, onOpened }: { crop: Crop; siteId: string; open: boolean; onClose: () => void; onOpened: (id: string) => void }) {
  const w = words(crop);
  const sites = useSites(crop);
  const [site, setSite] = useState(siteId);
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const openHeap = useOpenHeap();
  const already = useHeaps({ site_id: site, status: 'open' }, open && Boolean(site));
  useEffect(() => { if (open) { setSite(siteId); setNote(''); setError(null); } }, [open, siteId]);
  const openOnes = already.data ?? [];
  return (
    <Dialog open={open} onClose={onClose} title={`Open a new ${w.lotLower}`}
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button loading={openHeap.isPending} onClick={() => {
          if (!site) { setError(`Choose a ${w.siteLower}.`); return; }
          openHeap.mutate({ siteId: site, note: note.trim() || undefined }, {
            onSuccess: (r) => { toast.success(`${r.heap.heap_id} opened`); onOpened(r.heap.id); onClose(); },
            onError: (e) => setError(toApiError(e).message),
          });
        }}>Open {w.lotLower}</Button>
      </>}>
      <div className="flex flex-col gap-4">
        <FormField label={w.site} required error={error}>
          <Select value={site} placeholder={`Choose a ${w.siteLower}`} options={(sites.data ?? []).map((s) => ({ value: s.id, label: `${s.name} (${s.code})` }))} onChange={(e) => setSite(e.target.value)} />
        </FormField>
        {openOnes.length > 0 && (
          <p role="status" className="rounded-control border border-wheat-300 bg-wheat-50 px-3 py-2 text-sm text-ink">
            {openOnes.map((h) => h.heap_id).join(', ')} {openOnes.length === 1 ? 'is' : 'are'} already open here. You can still open another.
          </p>
        )}
        <FormField label="Note" hint="Optional.">
          <Textarea rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
        </FormField>
      </div>
    </Dialog>
  );
}
