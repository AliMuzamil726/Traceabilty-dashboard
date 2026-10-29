import { Check, Scale, Truck, X } from 'lucide-react';
import { formatNumber } from '@/core/utils/format';
import { StatCard } from '@/design-system/components';
import type { GateSummary } from '../api/types';
import { kgText } from '../lib/gate';

/** What is on the road, what is at the gate, and what today's decisions came to. */
export function GateKpis({ summary, loading }: { summary?: GateSummary; loading: boolean }) {
  const count = (value: number | undefined) => (value === undefined ? '-' : formatNumber(value));
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
      <StatCard
        label="Due to arrive"
        icon={<Truck />}
        loading={loading}
        value={count(summary?.inbound)}
        hint="In transit, not at the gate yet"
      />
      <StatCard
        label="At the gate"
        icon={<Scale />}
        loading={loading}
        value={count(summary?.pending)}
        hint="Waiting to be weighed"
      />
      <StatCard
        label="Accepted today"
        icon={<Check />}
        loading={loading}
        value={count(summary?.accepted_today)}
        hint="Loads received today"
      />
      <StatCard
        label="Rejected today"
        icon={<X />}
        loading={loading}
        value={count(summary?.rejected_today)}
        hint="Loads refused today"
      />
      <StatCard
        label="Net weight today"
        loading={loading}
        value={summary ? kgText(summary.net_kg_today) : '-'}
        hint="Accepted loads, gross minus tare"
      />
    </div>
  );
}
