import { ChevronRight, MapPin, NotebookPen, UserPlus } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { formatNumber } from '@/core/utils/format';
import { Skeleton } from '@/design-system/components/Skeleton';
import { AttentionPanel } from '../components/AttentionPanel';
import { useDashboardFilters } from '../hooks/useDashboardFilters';
import { useAlerts, useOverview } from '../hooks/useDashboardSection';

interface Action {
  to: string;
  title: string;
  detail: string;
  icon: LucideIcon;
  primary?: boolean;
}

/** The core workflows a field officer opens the app to do, plus their own numbers. */
const ACTIONS: Action[] = [
  {
    to: '/register/new',
    title: 'Register a farmer',
    detail: 'Enter the farmer, then map the field',
    icon: UserPlus,
    primary: true,
  },
  { to: '/fieldbook', title: 'Open a fieldbook', detail: 'Fill in this season, step by step', icon: NotebookPen },
  { to: '/register', title: 'My farmers', detail: 'Everyone I have registered', icon: MapPin },
];

function Tile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4 shadow-1 transition-shadow duration-base hover:shadow-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="tabular mt-1.5 text-2xl font-semibold tracking-[-0.02em] text-ink">{value}</p>
      <p className="mt-1 text-xs text-muted">{detail}</p>
    </div>
  );
}

/**
 * The field officer's home screen: built for a phone in a field, so it is one column
 * of large targets rather than the programme dashboard an office reads.
 */
export default function OfficerHomePage() {
  const { apiParams } = useDashboardFilters();
  const me = useCurrentOfficer();
  const overview = useOverview(apiParams);
  const alerts = useAlerts(apiParams);
  const k = overview.data?.kpis;

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-5 sm:px-6">
      <header>
        <h1 className="text-xl font-semibold tracking-[-0.01em] text-ink">
          {me.data ? me.data.full_name : 'My work'}
        </h1>
        <p className="mt-0.5 text-base text-muted">
          {me.data?.field_office_name ?? 'Field officer'}
        </p>
      </header>

      <ul className="flex flex-col gap-3">
        {ACTIONS.map((action) => (
          <li key={action.to}>
            <Link
              to={action.to}
              className={
                action.primary
                  ? 'flex items-center gap-4 rounded-card bg-forest-800 p-4 text-white shadow-2 transition-all duration-base ease-brand hover:bg-forest-700 hover:shadow-1 active:scale-[0.98]'
                  : 'flex items-center gap-4 rounded-card border border-line bg-surface p-4 text-ink shadow-1 transition-all duration-base ease-brand hover:shadow-2 hover:border-forest-200 active:scale-[0.98]'
              }
            >
              <span className={action.primary ? 'flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-white/10' : 'flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-forest-50'}>
                <action.icon className={action.primary ? 'h-5 w-5 text-wheat-300' : 'h-5 w-5 text-forest-700'} aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-md font-semibold">{action.title}</span>
                <span className={action.primary ? 'block text-sm text-forest-100/80' : 'block text-sm text-muted'}>
                  {action.detail}
                </span>
              </span>
              <ChevronRight className="h-5 w-5 shrink-0 opacity-40" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>

      <section aria-labelledby="my-figures">
        <h2 id="my-figures" className="mb-3 text-md font-semibold text-ink">
          My season
        </h2>
        {overview.isLoading && !k ? (
          <Skeleton className="h-28 w-full" />
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <Tile
              label="Farmers"
              value={formatNumber(k?.farmers.total ?? 0)}
              detail={`${formatNumber(k?.farmers.cotton ?? 0)} cotton, ${formatNumber(k?.farmers.hemp ?? 0)} hemp`}
            />
            <Tile
              label="Fields mapped"
              value={formatNumber(k?.fields.total ?? 0)}
              detail={`${formatNumber(k?.fields.area ?? 0, 2)} ${k?.fields.area_unit ?? ''}`}
            />
            <Tile
              label="Fieldbooks"
              value={formatNumber(k?.fieldbooks.submitted ?? 0)}
              detail={`submitted of ${formatNumber(k?.fieldbooks.fields ?? 0)} fields`}
            />
            <Tile
              label="Ready now"
              value={formatNumber(k?.ready_now.fields ?? 0)}
              detail="fields ready to pick"
            />
          </div>
        )}
      </section>

      <AttentionPanel
        data={alerts.data}
        loading={alerts.isLoading}
        error={alerts.error}
        onRetry={() => void alerts.refetch()}
      />
    </div>
  );
}
