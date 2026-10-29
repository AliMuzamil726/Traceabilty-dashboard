import { Truck } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { toApiError } from '@/core/api/errors';
import { useSites } from '@/core/hooks/useSharedData';
import { formatNumber } from '@/core/utils/format';
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SectionHeader,
  SegmentedControl,
  Select,
  Skeleton,
  buttonClasses,
} from '@/design-system/components';
import type { Crop } from '../api/types';
import { GateKpis } from '../components/GateKpis';
import { HistorySection } from '../components/HistorySection';
import { InboundSection } from '../components/InboundSection';
import { PendingSection } from '../components/PendingSection';
import { useGateSummary } from '../hooks/useGate';

/** One ginner's or processor's gate: arrivals, the queue at the gate, and today's decisions. */
export default function GatePage() {
  const [params, setParams] = useSearchParams();
  const crop: Crop = params.get('crop') === 'hemp' ? 'hemp' : 'cotton';
  const sites = useSites(crop);
  const requested = params.get('site');
  const siteId =
    requested && (sites.data ?? []).some((s) => s.id === requested)
      ? requested
      : sites.data?.[0]?.id ?? '';
  const summary = useGateSummary({ siteId, crop }, Boolean(siteId));

  const set = (changes: Record<string, string | null>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(changes)) {
          if (v) next.set(k, v);
          else next.delete(k);
        }
        return next;
      },
      { replace: true },
    );

  const waiting = summary.data?.pending;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Gate Reception"
        subtitle="Weigh in and accept the loads that Deliveries marked in transit."
        actions={
          <Link to={`/deliveries?tab=deliveries&crop=${crop}`} className={buttonClasses('secondary', 'sm')}>
            <Truck className="h-4 w-4" aria-hidden />
            Deliveries
          </Link>
        }
      />
      <section
        aria-label="Filters"
        className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface p-3"
      >
        <SegmentedControl
          aria-label="Crop"
          value={crop}
          onChange={(c) => set({ crop: c, site: null })}
          options={[
            { value: 'cotton', label: 'Cotton' },
            { value: 'hemp', label: 'Hemp' },
          ]}
        />
        <div className="w-full sm:w-60">
          <Select
            aria-label="Site"
            value={siteId}
            options={(sites.data ?? []).map((s) => ({ value: s.id, label: `${s.name} (${s.code})` }))}
            onChange={(e) => set({ site: e.target.value })}
          />
        </div>
      </section>

      {sites.isLoading ? (
        <Skeleton className="h-96 w-full" shape="block" />
      ) : sites.isError ? (
        <ErrorState
          title="Sites could not be loaded"
          description={toApiError(sites.error).message}
          onRetry={() => void sites.refetch()}
        />
      ) : !siteId ? (
        <EmptyState
          title={`No ${crop === 'cotton' ? 'ginner' : 'processor'} site`}
          description="Add a site for this crop before loads can arrive at its gate."
        />
      ) : (
        <>
          {summary.isError ? (
            <ErrorState
              title="Gate figures could not be loaded"
              description={toApiError(summary.error).message}
              onRetry={() => void summary.refetch()}
            />
          ) : (
            <GateKpis summary={summary.data} loading={summary.isLoading} />
          )}

          <Card padding="lg" as="section" aria-labelledby="gate-inbound-h" className="flex flex-col gap-3">
            <SectionHeader
              as="h2"
              id="gate-inbound-h"
              title="Due to arrive"
              actions={
                summary.data && (
                  <Badge tone="neutral">{formatNumber(summary.data.inbound)}</Badge>
                )
              }
            />
            <InboundSection siteId={siteId} crop={crop} />
          </Card>

          <Card padding="lg" as="section" aria-labelledby="gate-pending-h" className="flex flex-col gap-3">
            <SectionHeader
              as="h2"
              id="gate-pending-h"
              title="At the gate"
              actions={
                waiting !== undefined && (
                  <Badge tone={waiting > 0 ? 'warning' : 'neutral'}>{formatNumber(waiting)}</Badge>
                )
              }
            />
            <PendingSection siteId={siteId} crop={crop} />
          </Card>

          <Card padding="lg" as="section" aria-labelledby="gate-history-h" className="flex flex-col gap-3">
            <HistorySection siteId={siteId} crop={crop} />
          </Card>
        </>
      )}
    </div>
  );
}
