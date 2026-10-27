import { X } from 'lucide-react';
import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toApiError } from '@/core/api/errors';
import { useCurrentOfficer, useSites } from '@/core/hooks/useSharedData';
import { Button, EmptyState, PageHeader, SectionHeader, SegmentedControl, Select, Skeleton } from '@/design-system/components';
import type { Crop, Resolved } from '../api/types';
import { BalesTable } from '../components/BalesTable';
import { BaseUrlWarning } from '../components/BaseUrlWarning';
import { FindCodeBox } from '../components/FindCodeBox';
import { LotOverview } from '../components/LotOverview';
import { TraceExplorer } from '../components/TraceExplorer';
import { useBales, useLotOverview, useLots } from '../hooks/useLots';

/** Codes for every heap, batch and bale: print labels, find a code, trace back to the field. */
export default function QrTracingPage() {
  const [params, setParams] = useSearchParams();
  const crop: Crop = params.get('crop') === 'hemp' ? 'hemp' : 'cotton';
  const sites = useSites(crop);
  const siteId = params.get('site') ?? sites.data?.[0]?.id ?? '';
  const lots = useLots({ crop, site_id: siteId || undefined }, Boolean(siteId));
  const lotId = params.get('lot');
  const trace = params.get('trace');
  const overview = useLotOverview(lotId);
  const bales = useBales(lotId);
  const me = useCurrentOfficer();
  const kind = crop === 'cotton' ? 'Heap' : 'Batch';

  const set = (changes: Record<string, string | null>) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [k, v] of Object.entries(changes)) {
        if (v) next.set(k, v);
        else next.delete(k);
      }
      return next;
    }, { replace: true });

  useEffect(() => {
    if (!lotId && lots.data?.items[0]) set({ lot: lots.data.items[0].heap_id });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lots.data, lotId]);

  const onFound = (r: Resolved) => {
    const lotCrop = r.heap_id.startsWith('UK-') ? 'hemp' : crop;
    set({ crop: lotCrop === 'hemp' ? 'hemp' : null, site: null, lot: r.heap_id, trace: r.bale_serial ?? r.heap_id });
  };

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="QR tracing" subtitle="Every heap, batch and bale has a code. Print labels, and trace any code back to the farms it came from." />
      <BaseUrlWarning baseUrl={lots.data?.base_url} />
      <section aria-label="Filters" className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface p-3">
        <SegmentedControl aria-label="Crop" value={crop} onChange={(c) => set({ crop: c, site: null, lot: null, trace: null })}
          options={[{ value: 'cotton', label: 'Cotton' }, { value: 'hemp', label: 'Hemp' }]} />
        <div className="min-w-[220px]">
          <Select aria-label={crop === 'cotton' ? 'Ginner' : 'Processor'} value={siteId}
            options={(sites.data ?? []).map((s) => ({ value: s.id, label: `${s.name} (${s.code})` }))}
            onChange={(e) => set({ site: e.target.value, lot: null, trace: null })} />
        </div>
        <div className="min-w-[200px]">
          <Select aria-label={kind} value={lotId ?? ''} placeholder={lots.data?.items.length ? `Choose a ${kind.toLowerCase()}` : `No ${kind.toLowerCase()}s yet`}
            options={(lots.data?.items ?? []).map((l) => ({ value: l.heap_id, label: `${l.heap_id}${l.status === 'closed' ? ' (closed)' : ''}` }))}
            onChange={(e) => set({ lot: e.target.value || null, trace: null })} />
        </div>
      </section>
      <section aria-label="Find a code" className="rounded-card border border-line bg-surface p-3">
        <FindCodeBox onFound={onFound} />
      </section>

      {trace && (
        <section aria-labelledby="trace-h" className="flex flex-col gap-3">
          <SectionHeader id="trace-h" title={<>Trace of <span className="mono-id">{trace}</span></>}
            actions={<Button size="sm" variant="ghost" leftIcon={<X className="h-4 w-4" />} onClick={() => set({ trace: null })}>Close trace</Button>} />
          <TraceExplorer key={trace} target={trace.split('-').length >= 4 ? { kind: 'bale', serial: trace } : { kind: 'heap', heapId: trace }} />
        </section>
      )}

      {!lotId ? (
        <EmptyState title={`Choose a ${kind.toLowerCase()}`} description={`Codes appear here once a ${kind.toLowerCase()} is opened in Heap.`} />
      ) : overview.error ? (
        <EmptyState title="This lot cannot be shown" description={toApiError(overview.error).message} />
      ) : !overview.data ? (
        <Skeleton className="h-72 w-full" shape="block" />
      ) : (
        <>
          <LotOverview lot={overview.data} />
          <section aria-labelledby="bales-h" className="flex flex-col gap-3">
            <SectionHeader id="bales-h" title="Bales" actions={<Button size="sm" variant="ghost" onClick={() => set({ trace: overview.data?.heap_id ?? null })}>Trace this {kind.toLowerCase()}</Button>} />
            <BalesTable heapId={overview.data.heap_id} rows={bales.data ?? []} loading={bales.isLoading} isAdmin={Boolean(me.data?.is_admin)}
              onTrace={(serial) => set({ trace: serial })} />
          </section>
        </>
      )}
    </div>
  );
}
