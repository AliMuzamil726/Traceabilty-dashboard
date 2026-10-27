import { Download } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toApiError } from '@/core/api/errors';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { Button, PageHeader, Tabs, toast } from '@/design-system/components';
import { deliveriesApi } from '../api/client';
import { DeliveryDetail } from '../components/DeliveryDetail';
import { DeliveryFilters } from '../components/DeliveryFilters';
import { filtersFromUrl, toParams, type DeliveryFilterState } from '../lib/filters';
import { DeliveryKpis } from '../components/DeliveryKpis';
import { DeliveryList } from '../components/DeliveryList';
import { RequestsInbox } from '../components/RequestsInbox';
import { PAGE_SIZE, useDeliveryList, useDeliveryStats } from '../hooks/useDeliveries';
import { useInbox } from '../hooks/useInbox';

type View = 'inbox' | 'deliveries';

/** In transit: Radar requests become scheduled loads, then dispatch and gate receipt. */
export default function DeliveriesPage() {
  const [params, setParams] = useSearchParams();
  const view: View = params.get('tab') === 'deliveries' ? 'deliveries' : 'inbox';
  const selectedId = params.get('id');
  const me = useCurrentOfficer();
  const isAdmin = me.data?.is_admin ?? false;
  // A link (from the Dashboard, say) may open the list already filtered; after that the
  // filters are the page's own, as before.
  const [filters, setFilters] = useState<DeliveryFilterState>(() => filtersFromUrl(params));
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [filters]);

  const apiParams = useMemo(() => toParams(filters), [filters]);
  const stats = useDeliveryStats({ crop: apiParams.crop, scope: filters.scope });
  const inbox = useInbox({ crop: apiParams.crop, scope: filters.scope });
  const list = useDeliveryList({ ...apiParams, page });

  const go = (changes: Record<string, string | null>) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [k, v] of Object.entries(changes)) {
        if (v) next.set(k, v);
        else next.delete(k);
      }
      return next;
    }, { replace: true });

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="In Transit"
        subtitle="Schedule → In transit → Delivered. From farm to ginner or processor gate."
        actions={
          <Button variant="secondary" size="sm" leftIcon={<Download className="h-4 w-4" />}
            onClick={() => deliveriesApi.download('/export.csv', apiParams).catch((e: unknown) => toast.error('The export failed', toApiError(e).message))}>
            Export CSV
          </Button>
        }
      />
      <DeliveryKpis stats={stats.data} loading={stats.isLoading} showMaunds={filters.crop !== 'hemp'} />
      <Tabs
        aria-label="In Transit views"
        value={view}
        onChange={(tab) => go({ tab: tab === 'inbox' ? null : tab })}
        items={[
          { value: 'inbox', label: 'Requests inbox', count: inbox.data?.length },
          { value: 'deliveries', label: 'In Transit & delivered', count: list.data?.total },
        ]}
      >
        {(tab) => (
          <div className="mt-4">
            {tab === 'inbox' ? (
              <RequestsInbox items={inbox.data ?? []} loading={inbox.isLoading} />
            ) : (
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(280px,360px)_minmax(0,1fr)]">
                <div className="flex flex-col gap-4">
                  <DeliveryFilters value={filters} onChange={setFilters} isAdmin={isAdmin} />
                  <DeliveryList
                    items={list.data?.items ?? []}
                    counts={list.data?.status_counts}
                    status={filters.status}
                    onStatus={(status) => setFilters({ ...filters, status })}
                    selectedId={selectedId}
                    onSelect={(id) => go({ id })}
                    loading={list.isLoading}
                    page={page}
                    total={list.data?.total ?? 0}
                    pageSize={PAGE_SIZE}
                    onPage={setPage}
                  />
                </div>
                <DeliveryDetail id={selectedId} isAdmin={isAdmin} />
              </div>
            )}
          </div>
        )}
      </Tabs>
    </div>
  );
}
