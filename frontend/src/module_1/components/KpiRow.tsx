import { ClipboardCheck, MapPin, Scissors, Truck } from 'lucide-react';
import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { formatCompact, formatNumber } from '@/core/utils/format';
import { StatCard } from '@/design-system/components/StatCard';
import { listItemVariants } from '@/design-system/motion';
import type { Overview } from '../api/types';
import { area, mass, percent, pluralise } from '../lib/format';
import { useCountUp } from '../hooks/useCountUp';

export interface KpiRowProps {
  data: Overview | undefined;
  loading: boolean;
}

/** A KPI value that counts up once, then sits still. */
function Counted({ value, render }: { value: number; render: (n: number) => ReactNode }) {
  return <>{render(useCountUp(value))}</>;
}

const SLOTS = 4;

/**
 * The quantities a programme lead checks first. Units follow the crop: acres and
 * maunds for cotton, hectares and tonnes for hemp, as the server measured them.
 */
export function KpiRow({ data, loading }: KpiRowProps) {
  if (loading && !data) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: SLOTS }, (_, i) => (
          <StatCard key={i} label={`Key figure ${i + 1}`} loading />
        ))}
      </div>
    );
  }
  if (!data) return null;

  const k = data.kpis;
  const areaUnit = k.fields.area_unit;
  const massUnit = data.units.mass;
  // Farmers, fields, bales and scans are already counted in the pipeline above, so the
  // row carries the figures it does not: a rate, a quantity ready, a quantity moved.
  // The weight in the local unit (maunds, tonnes) is secondary: it moves to the hint line.
  const [deliveredKg, deliveredAlt] = mass(k.delivered.kg, massUnit).split(' (');
  const cards = [
    {
      label: 'Fieldbooks submitted',
      icon: <ClipboardCheck />,
      value: percent(k.fieldbooks.submitted_pct, 1),
      hint: `${formatNumber(k.fieldbooks.submitted)} of ${pluralise(k.fieldbooks.fields, 'field')}`,
    },
    {
      label: 'Ready for pickup now',
      icon: <Scissors />,
      value: <Counted value={k.ready_now.fields} render={(n) => formatNumber(n)} />,
      hint:
        k.ready_now.fields === 0
          ? 'Nothing waiting'
          : `${formatCompact(k.ready_now.estimated_kg)} kg estimated, ${formatNumber(
              k.ready_now.awaiting_pickup,
            )} not requested`,
    },
    {
      label: `Delivered, ${rangeWords(data.range.key, data.range.days)}`,
      icon: <Truck />,
      value: deliveredKg,
      hint:
        k.delivered.deliveries === 0
          ? 'No loads weighed in'
          : `${deliveredAlt ? `${deliveredAlt.replace(')', '')}, ` : ''}${pluralise(k.delivered.deliveries, 'load')}${
              k.delivered.average_moisture_pct === null
                ? ''
                : `, ${percent(k.delivered.average_moisture_pct, 1)} average moisture`
            }`,
    },
    {
      label: 'Mapped area',
      icon: <MapPin />,
      value: area(k.fields.area, areaUnit, 2),
      hint: `${formatNumber(k.fields.total)} fields, ${formatNumber(k.farmers.total)} farmers`,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card, index) => (
        <motion.div
          key={card.label}
          custom={index}
          variants={listItemVariants}
          initial="initial"
          animate="animate"
          className="h-full"
        >
          <StatCard className="h-full" label={card.label} value={card.value} hint={card.hint} icon={card.icon} />
        </motion.div>
      ))}
    </div>
  );
}

function rangeWords(key: string, days: number): string {
  if (key === 'season') return 'this season';
  if (key === 'custom') return `${days} days`;
  return `last ${days} days`;
}
