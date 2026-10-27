import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Distribution } from '../api/types';
import { HEX } from '../lib/format';
import { axisStyle, gridStyle, tooltipStyle } from '../lib/charts';

/**
 * How far the season's fieldbooks have got, step by step.
 *
 * Drawn as horizontal bars in the form's own order: a step that drops sharply is where
 * the officers are getting stuck, and the step names are too long to fit upright.
 */
export default function FunnelChart({ data }: { data: Distribution }) {
  const rows = [...data.fieldbook_funnel]
    .sort((a, b) => a.order - b.order)
    .map((step) => ({ label: step.title, complete: step.complete, pct: step.pct }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid horizontal={false} {...gridStyle} />
        <XAxis type="number" allowDecimals={false} {...axisStyle} axisLine={false} />
        <YAxis type="category" dataKey="label" width={132} {...axisStyle} />
        <Tooltip
          {...tooltipStyle}
          formatter={(value: number, _name, item) => [
            `${value} fieldbooks (${(item.payload as { pct: number }).pct}%)`,
            'Finished',
          ]}
        />
        <Bar
          dataKey="complete"
          name="Finished"
          fill={HEX.forest600}
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
