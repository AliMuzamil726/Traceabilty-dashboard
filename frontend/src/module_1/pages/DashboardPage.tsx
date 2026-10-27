import { lazy, Suspense } from 'react';
import { PageContainer } from '@/app/layout/PageContainer';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { SectionHeader } from '@/design-system/components/Card';
import { PageSkeleton } from '@/shared/components/PageSkeleton';
import { DashboardHeader } from '../components/DashboardHeader';
import { KpiRow } from '../components/KpiRow';
import { OfficerTable } from '../components/OfficerTable';
import { PipelineTracker } from '../components/PipelineTracker';
import { SectionCard, SectionError } from '../components/SectionCard';
import { useDashboardFilters } from '../hooks/useDashboardFilters';
import {
  useDashboardMap,
  useOfficerOverview,
  useOverview,
  usePipeline,
} from '../hooks/useDashboardSection';
import { CROP_LABEL } from '../lib/format';

// The map is the heavy part of the page: it loads on its own.
const OverviewMap = lazy(() => import('../components/OverviewMap'));
// A field officer gets a phone-first screen instead of the programme dashboard.
const OfficerHomePage = lazy(() => import('./OfficerHomePage'));

/**
 * The home screen. Every section is its own request with its own loading, error and
 * retry, so one slow or failing part never holds up the rest.
 *
 * Changing crop / season / range fully refreshes every section (loading state + new data).
 */
export default function DashboardPage() {
  const { filters, apiParams, rangeIncomplete, update } = useDashboardFilters();
  const me = useCurrentOfficer();
  const isAdmin = me.data?.sees_all ?? me.data?.is_admin ?? false;
  const isFieldOfficer = me.data?.role === 'officer';

  const overview = useOverview(apiParams);
  const pipeline = usePipeline(apiParams);
  const map = useDashboardMap(apiParams);
  const officers = useOfficerOverview(apiParams, isAdmin);

  // Show loading whenever a filter change is in flight, not only on the first load.
  const overviewLoading = overview.isLoading || overview.isFetching;
  const pipelineLoading = pipeline.isLoading || pipeline.isFetching;
  const mapLoading = map.isLoading || map.isFetching;
  const officersLoading = officers.isLoading || officers.isFetching;

  if (isFieldOfficer) {
    return (
      <Suspense fallback={<PageSkeleton />}>
        <OfficerHomePage />
      </Suspense>
    );
  }

  return (
    <PageContainer>
      <DashboardHeader filters={filters} onChange={update} rangeIncomplete={rangeIncomplete} />

      <section className="mt-6" aria-labelledby="kpi-heading">
        <h2 id="kpi-heading" className="sr-only">
          Key figures
        </h2>
        {overview.error ? (
          <SectionError error={overview.error} onRetry={() => void overview.refetch()} />
        ) : (
          <KpiRow data={overview.data} loading={overviewLoading} />
        )}
      </section>

      <section className="mt-8" aria-labelledby="workflow-heading">
        <SectionHeader
          id="workflow-heading"
          title="Traceability Stages"
          description={`${CROP_LABEL[filters.crop]}, season ${filters.season}.`}
          className="mb-4"
        />
        {pipeline.error ? (
          <SectionError error={pipeline.error} onRetry={() => void pipeline.refetch()} />
        ) : (
          <PipelineTracker data={pipeline.data} loading={pipelineLoading} />
        )}
      </section>

      <div className="mt-8 min-w-0">
        <SectionCard
          id="map-heading"
          title="Fields on the map"
          description="Click a field for its ID, farmer, area and status."
          error={map.error}
          onRetry={() => void map.refetch()}
        >
          <OverviewMap crop={filters.crop} data={map.data} loading={mapLoading} />
        </SectionCard>
      </div>

      {isAdmin && (
        <div className="mt-6">
          <OfficerTable
            data={officers.data}
            loading={officersLoading}
            error={officers.error}
            onRetry={() => void officers.refetch()}
          />
        </div>
      )}
    </PageContainer>
  );
}
