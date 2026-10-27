import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatNumber } from '@/core/utils/format';
import type { CalendarData } from '../api/types';
import { HEX } from '../lib/status';

function weekLabel(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

/** Estimated quantity becoming ready each week, for the next eight weeks. */
export function DemandChart({ weeks }: { weeks: CalendarData['weeks'] | undefined }) {
  const data = (weeks ?? []).map((w) => ({ ...w, label: weekLabel(w.week_start), tonnes: Math.round(w.estimated_kg / 100) / 10 }));
  const total = data.reduce((sum, w) => sum + w.estimated_kg, 0);
  return (
    <section aria-labelledby="demand-title" className="rounded-card border border-line bg-surface p-4">
      <h2 id="demand-title" className="text-md font-semibold text-ink">
        Demand, next 8 weeks
      </h2>
      <p className="text-sm text-muted">Estimated quantity becoming ready each week: {formatNumber(total / 1000, 1)} t in all.</p>
      <div className="mt-3 h-56" role="img" aria-label={data.map((w) => `Week of ${w.label}: ${w.tonnes} t`).join('. ')}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -12 }}>
            <CartesianGrid vertical={false} stroke={HEX.line} />
            <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: HEX.line }} tick={{ fill: HEX.muted, fontSize: 12 }} />
            <YAxis tickLine={false} axisLine={false} tick={{ fill: HEX.muted, fontSize: 12 }} unit=" t" />
            <Tooltip
              cursor={{ fill: HEX.wheat300, fillOpacity: 0.25 }}
              formatter={(value: number, _name, item) => [`${value} t, ${(item.payload as { fields: number }).fields} fields`, 'Estimated']}
              contentStyle={{ borderColor: HEX.line, borderRadius: 8, fontSize: 13 }}
            />
            <Bar dataKey="tonnes" fill={HEX.forest600} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
