import { AlertTriangle, CalendarCheck, Inbox, PackageCheck, Truck } from 'lucide-react';
import { formatNumber } from '@/core/utils/format';
import { StatCard } from '@/design-system/components';
import type { Stats } from '../api/types';

export function DeliveryKpis({ stats, loading, showMaunds }: { stats: Stats | undefined; loading: boolean; showMaunds: boolean }) {
  const count = (value: number | undefined) => (value === undefined ? '-' : formatNumber(value));
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" aria-label="Key figures">
      <StatCard loading={loading} label="Requests waiting" icon={<Inbox />} value={count(stats?.requests_waiting)} hint="From Harvest Radar" />
      <StatCard loading={loading} label="Scheduled" icon={<CalendarCheck />} value={count(stats?.scheduled)} />
      <StatCard loading={loading} label="In transit" icon={<Truck />} value={count(stats?.in_transit)} />
      <StatCard
        loading={loading}
        label="Delivered this week"
        icon={<PackageCheck />}
        value={count(stats?.delivered_this_week)}
        hint={stats && `${formatNumber(stats.delivered_this_week_kg)} kg${showMaunds && stats.delivered_this_week_maunds !== null ? `, ${formatNumber(stats.delivered_this_week_maunds, 1)} maunds` : ''}`}
      />
      <StatCard loading={loading} label="Weight flags" icon={<AlertTriangle />} value={count(stats?.weight_flags)} hint="Weighbridge beyond the flag limit" />
    </div>
  );
}
