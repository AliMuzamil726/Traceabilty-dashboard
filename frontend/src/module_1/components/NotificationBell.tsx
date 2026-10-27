import { Bell, CircleCheck, History } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { toApiError } from '@/core/api/errors';
import { cn } from '@/core/utils/cn';
import { formatDateTime, formatNumber } from '@/core/utils/format';
import { Select } from '@/design-system/components/Select';
import { Skeleton } from '@/design-system/components/Skeleton';
import { useActivity, useAlerts } from '../hooks/useDashboardSection';
import { useDashboardFilters } from '../hooks/useDashboardFilters';
import { relativeTime } from '../lib/format';
import { toHref } from '../lib/links';
import { AlertRow } from './AlertRow';

type Tab = 'attention' | 'activity';

/**
 * The top bar's bell: "Needs attention" and "Recent activity" live here instead of taking
 * a column beside the map. The badge counts what needs attention; red when any is critical.
 */
export function NotificationBell() {
  const { apiParams } = useDashboardFilters();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>('attention');
  const [module, setModule] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  const alerts = useAlerts(apiParams);
  const activity = useActivity(apiParams, module);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const raised = (alerts.data?.alerts ?? [])
    .filter((alert) => alert.count > 0)
    .sort((a, b) => {
      if (a.severity !== b.severity) return a.severity === 'critical' ? -1 : 1;
      return b.count - a.count;
    });
  const total = alerts.data?.total ?? 0;
  const critical = (alerts.data?.critical ?? 0) > 0;

  const tabClass = (active: boolean) =>
    cn(
      'flex-1 rounded-control px-3 py-1.5 text-sm font-medium transition-colors duration-fast',
      active ? 'bg-forest-50 text-forest-800' : 'text-muted hover:bg-canvas',
    );

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={total > 0 ? `Notifications, ${total} need attention` : 'Notifications'}
        className="relative inline-flex h-10 w-10 items-center justify-center rounded-control text-muted transition-colors duration-fast hover:bg-forest-50 hover:text-forest-800"
      >
        <Bell className="h-5 w-5" aria-hidden />
        {total > 0 && (
          <span
            className={cn(
              'absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-pill px-1 text-[10px] font-semibold leading-none text-white',
              critical ? 'bg-danger' : 'bg-wheat-600',
            )}
          >
            {total > 99 ? '99+' : total}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="fixed left-3 right-3 top-[68px] z-40 flex max-h-[75vh] flex-col overflow-hidden rounded-card border border-line bg-surface shadow-2 sm:absolute sm:left-auto sm:right-0 sm:top-full sm:mt-2 sm:w-[420px]"
        >
          <div className="flex gap-1 border-b border-line p-2">
            <button type="button" className={tabClass(tab === 'attention')} onClick={() => setTab('attention')}>
              Needs attention{total > 0 ? ` (${formatNumber(total)})` : ''}
            </button>
            <button type="button" className={tabClass(tab === 'activity')} onClick={() => setTab('activity')}>
              Recent activity
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {tab === 'attention' ? (
              alerts.error ? (
                <Problem error={alerts.error} onRetry={() => void alerts.refetch()} />
              ) : alerts.isLoading && !alerts.data ? (
                <Skeleton className="h-40 w-full" shape="block" />
              ) : raised.length === 0 ? (
                <Empty icon={<CircleCheck className="h-5 w-5" />} title="Nothing needs attention" text="Every rule is clear for this crop and season." />
              ) : (
                <ul className="flex flex-col gap-2">
                  {raised.map((alert, index) => (
                    <AlertRow key={alert.key} alert={alert} index={index} />
                  ))}
                </ul>
              )
            ) : (
              <>
                <Select
                  aria-label="Filter activity by module"
                  value={module === null ? '' : String(module)}
                  onChange={(e) => setModule(e.target.value === '' ? null : Number(e.target.value))}
                  options={[
                    { value: '', label: 'Every module' },
                    ...(activity.data?.modules ?? []).map((m) => ({ value: String(m.number), label: m.name })),
                  ]}
                  className="mb-3 h-9 w-full"
                />
                {activity.error ? (
                  <Problem error={activity.error} onRetry={() => void activity.refetch()} />
                ) : activity.isLoading && !activity.data ? (
                  <Skeleton className="h-40 w-full" shape="block" />
                ) : (activity.data?.items.length ?? 0) === 0 ? (
                  <Empty icon={<History className="h-5 w-5" />} title="Nothing recorded yet" text="Changes appear here as officers register farmers and fill in fieldbooks." />
                ) : (
                  <ol className="flex flex-col">
                    {(activity.data?.items ?? []).map((item) => (
                      <li key={item.id} className="border-b border-line/60 py-2.5 last:border-0 last:pb-0">
                        <RouterLink to={toHref(item.link)} onClick={() => setOpen(false)} className="group flex flex-col gap-0.5">
                          <span className="flex flex-wrap items-baseline gap-x-2">
                            <span className="font-medium text-ink group-hover:underline">{item.summary}</span>
                            <span className="text-xs text-muted">{item.module_name}</span>
                          </span>
                          <span className="text-sm text-muted">
                            {item.officer_name ?? 'System'}
                            {' · '}
                            <time dateTime={item.at} title={formatDateTime(item.at)}>
                              {relativeTime(item.at)}
                            </time>
                          </span>
                        </RouterLink>
                      </li>
                    ))}
                  </ol>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Empty({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-forest-50 text-forest-700">{icon}</span>
      <p className="font-medium text-ink">{title}</p>
      <p className="text-sm text-muted">{text}</p>
    </div>
  );
}

function Problem({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  return (
    <div role="alert" className="rounded-control border border-line bg-canvas p-3 text-sm text-ink">
      <p>This section could not be loaded. {toApiError(error).message}</p>
      <button type="button" onClick={onRetry} className="mt-2 font-medium text-forest-700 hover:underline">
        Try again
      </button>
    </div>
  );
}
