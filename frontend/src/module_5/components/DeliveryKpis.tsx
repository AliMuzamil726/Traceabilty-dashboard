import { AlertTriangle, CalendarCheck, Inbox, PackageCheck, Truck } from 'lucide-react';
import { formatNumber } from '@/core/utils/format';
import { StatCard } from '@/design-system/components';
import type { Stats } from '../api/types';

export function DeliveryKpis({ stats, loading, showMaunds }: { stats: Stats | undefined; loading: boolean; showMaunds: boolean }) {
  const s = stats;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" aria-label="Key figures">
      <StatCard loading={loading || !s} label="Requests waiting" icon={<Inbox />} value={s && formatNumber(s.requests_waiting)} hint="From Harvest Radar" />
      <StatCard loading={loading || !s} label="Scheduled" icon={<CalendarCheck />} value={s && formatNumber(s.scheduled)} />
      <StatCard loading={loading || !s} label="In transit" icon={<Truck />} value={s && formatNumber(s.in_transit)} />
      <StatCard
        loading={loading || !s}
        label="Delivered this week"
        icon={<PackageCheck />}
        value={s && formatNumber(s.delivered_this_week)}
        hint={s && `${formatNumber(s.delivered_this_week_kg)} kg${showMaunds && s.delivered_this_week_maunds !== null ? `, ${formatNumber(s.delivered_this_week_maunds, 1)} maunds` : ''}`}
      />
      <StatCard loading={loading || !s} label="Weight flags" icon={<AlertTriangle />} value={s && formatNumber(s.weight_flags)} hint="Weighbridge beyond the flag limit" />
    </div>
  );
}
