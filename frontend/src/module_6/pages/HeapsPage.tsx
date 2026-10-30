import { Download, Inbox, Plus } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { buildUrl, OFFICER_HEADER } from '@/core/api/client';
import { toApiError } from '@/core/api/errors';
import { useSites } from '@/core/hooks/useSharedData';
import { useOfficerStore } from '@/core/store/officerStore';
import { cn } from '@/core/utils/cn';
import { Button, Card, EmptyState, PageHeader, SectionHeader, SegmentedControl, Select, Skeleton, toast } from '@/design-system/components';
import { heapsApi } from '../api/client';
import type { Crop } from '../api/types';
import { BalesPanel } from '../components/BalesPanel';
import { CloseHeapDialog } from '../components/CloseHeapDialog';
import { ContributionTable } from '../components/ContributionTable';
import { DeliveriesTable } from '../components/DeliveriesTable';
import { HeapHeader } from '../components/HeapHeader';
import { HeapKpis } from '../components/HeapKpis';
import { HeapList } from '../components/HeapList';
import { OpenHeapDialog } from '../components/OpenHeapDialog';
import { ReceiveDeliveriesDrawer } from '../components/ReceiveDeliveriesDrawer';
import { useHeapDetail } from '../hooks/useHeapDetail';
import { useHeaps } from '../hooks/useHeaps';
import { words } from '../lib/wording';

type StatusFilter = 'open' | 'closed' | 'all';

async function downloadCsv(key: string) {
  const officerId = useOfficerStore.getState().officerId;
  const res = await fetch(buildUrl(heapsApi.exportCsvUrl(key)), { headers: officerId ? { [OFFICER_HEADER]: officerId } : {} });
  if (!res.ok) throw new Error('The export failed.');
  const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'heap.csv';
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/** Heaps (cotton, at ginners) and batches (hemp, at processors). */
export default function HeapsPage() {
  const [params, setParams] = useSearchParams();
  const crop: Crop = params.get('crop') === 'hemp' ? 'hemp' : 'cotton';
  const status = (['open', 'closed', 'all'].includes(params.get('status') ?? '') ? params.get('status') : 'open') as StatusFilter;
  const selected = params.get('heap');
  const sites = useSites(crop);
  const requestedSite = params.get('site');
  /* No ginner chosen means every ginner. Defaulting to the first one hides the other
     sites' heaps and looks like the site filter has stopped working. */
  const siteId = requestedSite && (sites.data ?? []).some((s) => s.id === requestedSite) ? requestedSite : '';
  const w = words(crop);
  const [opening, setOpening] = useState(false);
  const [receiving, setReceiving] = useState(false);

  const set = (changes: Record<string, string | null>) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [k, v] of Object.entries(changes)) {
        if (v) next.set(k, v);
        else next.delete(k);
      }
      return next;
    }, { replace: true });

  const heaps = useHeaps({ crop, site_id: siteId || undefined, status: status === 'all' ? undefined : status });
  const detail = useHeapDetail(selected);
  const heap = detail.data;

  useEffect(() => {
    if (!selected && heaps.data?.[0]) set({ heap: heaps.data[0].id });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heaps.data, selected]);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={w.lots} subtitle={`Gather delivered ${crop} into ${w.lots.toLowerCase()}, record the bales made, and close.`} />
      <section aria-label="Filters" className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface p-3">
        <SegmentedControl aria-label="Crop" value={crop} onChange={(c) => set({ crop: c, site: null, heap: null })}
          options={[{ value: 'cotton', label: 'Cotton' }, { value: 'hemp', label: 'Hemp' }]} />
        <div className="min-w-0 min-w-[200px] flex-1 sm:flex-none sm:w-60">
          <Select
            aria-label={w.site}
            value={siteId}
            placeholder={`All ${w.siteLower}s`}
            options={(sites.data ?? []).map((s) => ({ value: s.id, label: `${s.name} (${s.code})` }))}
            onChange={(e) => set({ site: e.target.value, heap: null })}
          />
        </div>
        <div role="group" aria-label="Status" className="flex gap-1.5">
          {(['open', 'closed', 'all'] as const).map((s) => (
            <button key={s} type="button" aria-pressed={status === s} onClick={() => set({ status: s === 'open' ? null : s, heap: null })}
              className={cn('rounded-full border px-3 py-1 text-xs font-medium', status === s ? 'border-forest-700 bg-forest-700 text-white' : 'border-line bg-surface text-ink hover:border-forest-500')}>
              {s === 'open' ? 'Open' : s === 'closed' ? 'Closed' : 'All'}
            </button>
          ))}
        </div>
        <span className="flex-1" />
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setOpening(true)}>Open new {w.lotLower}</Button>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(260px,320px)_minmax(0,1fr)]">
        {!heaps.isLoading && (heaps.data ?? []).length === 0 && !selected ? (
          <div className="lg:col-span-2">
            <EmptyState
              title={`No ${w.lots.toLowerCase()}${siteId ? ` at this ${w.siteLower}` : ' yet'}`}
              description={`Open a ${w.lotLower} to start gathering deliveries.`}
            />
          </div>
        ) : (
          <>
            <HeapList
              crop={crop}
              heaps={heaps.data ?? []}
              loading={heaps.isLoading}
              selected={selected}
              onSelect={(id) => set({ heap: id })}
              siteName={(h) => (sites.data ?? []).find((s) => s.id === h.site_id)?.name ?? null}
            />
            {!selected ? (
              <EmptyState title={`Choose a ${w.lotLower}`} description={`Select a ${w.lotLower} on the left, or open a new one.`} />
            ) : detail.error ? (
              <EmptyState title={`This ${w.lotLower} cannot be opened`} description={toApiError(detail.error).message} />
            ) : !heap ? (
              <Skeleton className="h-96 w-full" shape="block" />
            ) : (
              <Card padding="lg" as="section" aria-label={heap.heap_id} className="flex flex-col gap-6">
                <HeapHeader heap={heap} />
                <HeapKpis heap={heap} />
                <section aria-labelledby="deliveries-h" className="flex flex-col gap-3">
                  <SectionHeader as="h3" id="deliveries-h" title="Deliveries"
                    actions={heap.permissions.can_add_deliveries && (
                      <Button size="sm" variant="secondary" leftIcon={<Inbox className="h-4 w-4" />} onClick={() => setReceiving(true)}>
                        Receive deliveries ({heap.pending_deliveries.length})
                      </Button>
                    )} />
                  <DeliveriesTable heap={heap} />
                </section>
                <section aria-labelledby="contrib-h" className="flex flex-col gap-3">
                  <SectionHeader as="h3" id="contrib-h" title="Farmer contribution" />
                  <ContributionTable rows={heap.contributions} />
                </section>
                <section aria-labelledby="bales-h" className="flex flex-col gap-3">
                  <SectionHeader as="h3" id="bales-h" title="Bales" />
                  <BalesPanel heap={heap} />
                </section>
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
                  <Button size="sm" variant="ghost" leftIcon={<Download className="h-4 w-4" />}
                    onClick={() => downloadCsv(heap.id).catch((e: unknown) => toast.error('The export failed', toApiError(e).message))}>
                    Export CSV
                  </Button>
                  <CloseHeapDialog heap={heap} />
                </div>
                <ReceiveDeliveriesDrawer heap={heap} open={receiving} onClose={() => setReceiving(false)} />
              </Card>
            )}
          </>
        )}
      </div>
      <OpenHeapDialog crop={crop} siteId={siteId} open={opening} onClose={() => setOpening(false)} onOpened={(id) => set({ heap: id, status: null })} />
    </div>
  );
}
