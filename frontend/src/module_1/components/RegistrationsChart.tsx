import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Timeseries } from '../api/types';
import { HEX, shortDate } from '../lib/format';
import { axisStyle, gridStyle, tooltipStyle } from '../lib/charts';

/** Farmers registered and fields mapped over the range, read side by side. */
export default function RegistrationsChart({ data }: { data: Timeseries }) {
  const farmers = data.series.find((s) => s.key === 'farmers');
  const fields = data.series.find((s) => s.key === 'fields');
  const rows = (farmers?.points ?? []).map((point, index) => ({
    label: shortDate(point.period_start),
    farmers: point.value ?? 0,
    fields: fields?.points[index]?.value ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} {...gridStyle} />
        <XAxis dataKey="label" {...axisStyle} />
        <YAxis allowDecimals={false} {...axisStyle} axisLine={false} />
        <Tooltip {...tooltipStyle} />
        <Legend
          verticalAlign="top"
          align="left"
          height={28}
          iconType="plainline"
          wrapperStyle={{ fontSize: 13, color: HEX.muted }}
        />
        <Line
          type="monotone"
          dataKey="farmers"
          name="Farmers registered"
          stroke={HEX.forest700}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="fields"
          name="Fields mapped"
          stroke={HEX.wheat600}
          strokeWidth={2}
          strokeDasharray="5 3"
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
