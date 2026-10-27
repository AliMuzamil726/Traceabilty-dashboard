import { Leaf, ShieldCheck, TriangleAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { ApiError } from '@/core/api/errors';
import { formatDate, formatNumber } from '@/core/utils/format';
import { Skeleton } from '@/design-system/components';
import type { PublicTrace } from '../api/types';
import { ChainStepper } from '../components/ChainStepper';
import { VerificationPanel } from '../components/VerificationPanel';
import { usePublicTrace } from '../hooks/usePublicTrace';

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="bg-forest-900 text-white">
        <div className="mx-auto flex max-w-xl items-center gap-2 px-4 py-3">
          <Leaf aria-hidden className="h-5 w-5 text-wheat-300" />
          <span className="font-semibold tracking-wide">SAWIE</span>
          <span className="text-sm text-forest-100">Fibre traceability</span>
        </div>
      </header>
      <main className="mx-auto flex max-w-xl flex-col gap-4 px-4 py-5">{children}</main>
      <footer className="mx-auto max-w-xl px-4 pb-8 text-xs text-muted">
        This page shows where the fibre came from without naming farmers or showing exact locations.
      </footer>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line py-2 text-sm last:border-b-0">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium text-ink">{value}</dd>
    </div>
  );
}

function range(from: string | null, to: string | null): string {
  if (!from) return 'Not recorded';
  const a = formatDate(from);
  const b = to ? formatDate(to) : a;
  return a === b ? a : `${a} to ${b}`;
}

export function PublicTraceView({ data }: { data: PublicTrace }) {
  const allPassed = data.checks.every((c) => c.passed);
  return (
    <>
      <section aria-label="Product" className="rounded-card border border-line bg-surface p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-forest-700">{data.programme}</p>
        <h1 className="mt-1 text-xl font-semibold text-ink">{data.product}</h1>
        {data.bale_serial && <p className="mono-id mt-1 text-sm text-muted">{data.bale_serial}</p>}
        <p className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${allPassed ? 'bg-forest-50 text-forest-700' : 'bg-wheat-100 text-ink'}`}>
          {allPassed ? <ShieldCheck aria-hidden className="h-3.5 w-3.5" /> : <TriangleAlert aria-hidden className="h-3.5 w-3.5 text-wheat-600" />}
          {allPassed ? 'All checks passed' : 'Some checks have not passed yet'}
        </p>
        <dl className="mt-3">
          {data.weight_kg !== null && <Fact label="Weight" value={`${formatNumber(data.weight_kg)} kg`} />}
          <Fact label={data.lot_kind} value={<span className="mono-id">{data.lot_id}</span>} />
          {data.season_year && <Fact label="Season" value={data.season_year} />}
          <Fact label={data.site.type} value={`${data.site.name ?? '-'}${data.site.region ? `, ${data.site.region}` : ''}`} />
          <Fact label="Processing" value={range(data.processing.opened, data.processing.closed)} />
          <Fact label="Country" value={data.country} />
        </dl>
      </section>
      <section aria-label="Origin" className="rounded-card border border-line bg-surface p-4">
        <h2 className="text-base font-semibold text-ink">Where it was grown</h2>
        <dl className="mt-2">
          <Fact label="Farms" value={formatNumber(data.farms)} />
          <Fact label="Fields" value={formatNumber(data.fields)} />
          <Fact label={data.regions.length === 1 ? data.region_level : `${data.region_level === 'County' ? 'Counties' : 'Districts'}`}
            value={data.regions.length ? data.regions.join(', ') : '-'} />
          <Fact label="Harvest" value={range(data.harvest_window.from, data.harvest_window.to)} />
        </dl>
      </section>
      <section aria-label="Journey" className="rounded-card border border-line bg-surface p-4">
        <h2 className="mb-3 text-base font-semibold text-ink">From field to {data.bale_serial ? 'bale' : data.lot_kind.toLowerCase()}</h2>
        <ChainStepper steps={data.timeline} />
      </section>
      <VerificationPanel checks={data.checks} />
    </>
  );
}

/** What anyone sees after scanning a label. No login, no sidebar, no personal data. */
export default function PublicTracePage() {
  const { token = '' } = useParams();
  const q = usePublicTrace(token);
  if (q.isLoading) {
    return (
      <Frame>
        <div aria-busy="true" aria-label="Loading" className="flex flex-col gap-4">
          <Skeleton className="h-48 w-full" shape="block" />
          <Skeleton className="h-64 w-full" shape="block" />
        </div>
      </Frame>
    );
  }
  if (q.error || !q.data) {
    const err = q.error instanceof ApiError ? q.error : null;
    const title = err?.status === 404 ? 'This code is not valid' : err?.status === 429 ? 'Too many lookups' : 'This page could not be loaded';
    const body = err?.status === 404
      ? 'Check that the whole code was scanned. A code that has been withdrawn also shows this message.'
      : err?.status === 429 ? 'Wait a minute and try again.' : 'Check your connection and try again.';
    return (
      <Frame>
        <section role="alert" className="rounded-card border border-line bg-surface p-6 text-center">
          <TriangleAlert aria-hidden className="mx-auto h-8 w-8 text-wheat-600" />
          <h1 className="mt-3 text-lg font-semibold text-ink">{title}</h1>
          <p className="mt-1 text-sm text-muted">{body}</p>
        </section>
      </Frame>
    );
  }
  return <Frame><PublicTraceView data={q.data} /></Frame>;
}
