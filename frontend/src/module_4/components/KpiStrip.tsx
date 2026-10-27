import { animate, useReducedMotion } from 'framer-motion';
import { AlarmClock, CalendarClock, CheckCircle2, Truck } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { formatNumber } from '@/core/utils/format';
import { StatCard } from '@/design-system/components';
import { DURATION, EASE } from '@/design-system/motion';
import type { Kpis, Totals } from '../api/types';

/** A number that eases to its new value; instant when the officer prefers reduced motion. */
export function CountUp({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (reduce) {
      setShown(value);
      from.current = value;
      return undefined;
    }
    const controls = animate(from.current, value, {
      duration: DURATION.slow * 2,
      ease: EASE,
      onUpdate: (v) => setShown(v),
    });
    from.current = value;
    return () => controls.stop();
  }, [value, reduce]);
  return <>{formatNumber(shown, decimals)}</>;
}

function tonnes(kg: number): string {
  return kg >= 1000 ? `${formatNumber(kg / 1000, 1)} t` : `${formatNumber(kg)} kg`;
}

function detail(t: Totals, unit: string): string {
  return `${formatNumber(t.area, 1)} ${unit === 'acre' ? 'acres' : 'ha'}, about ${tonnes(t.estimated_kg)}`;
}

export function KpiStrip({ kpis, unit, loading }: { kpis: Kpis | undefined; unit: string; loading: boolean }) {
  const k = kpis;
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Key figures">
      <StatCard loading={loading || !k} label="Ready now" icon={<CheckCircle2 />} value={k && <CountUp value={k.ready_now.fields} />} hint={k && detail(k.ready_now, unit)} />
      <StatCard
        loading={loading || !k}
        label={`Ready within ${k?.approaching_window_days ?? 14} days`}
        icon={<CalendarClock />}
        value={k && <CountUp value={k.approaching_soon.fields} />}
        hint={k && detail(k.approaching_soon, unit)}
      />
      <StatCard loading={loading || !k} label="Pickup requested" icon={<Truck />} value={k && <CountUp value={k.pickup_requested.fields} />} hint={k && detail(k.pickup_requested, unit)} />
      <StatCard loading={loading || !k} label="Overdue" icon={<AlarmClock />} value={k && <CountUp value={k.overdue.fields} />} hint={k && 'Past the harvest window, not harvested'} />
    </div>
  );
}
