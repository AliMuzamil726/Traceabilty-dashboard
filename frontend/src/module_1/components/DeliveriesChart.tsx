import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Timeseries } from '../api/types';
import { HEX, shortDate, tonnes } from '../lib/format';
import { axisStyle, gridStyle, tooltipStyle } from '../lib/charts';

/** Delivered quantity per period, with the average moisture of the same loads. */
export default function DeliveriesChart({ data }: { data: Timeseries }) {
  const weight = data.series.find((s) => s.key === 'delivered_kg');
  const moisture = data.series.find((s) => s.key === 'average_moisture_pct');
  const rows = (weight?.points ?? []).map((point, index) => ({
    label: shortDate(point.period_start),
    tonnes: tonnes(point.value ?? 0),
    moisture: moisture?.points[index]?.value ?? null,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} {...gridStyle} />
        <XAxis dataKey="label" {...axisStyle} />
        <YAxis yAxisId="weight" {...axisStyle} axisLine={false} unit=" t" />
        <YAxis
          yAxisId="moisture"
          orientation="right"
          {...axisStyle}
          axisLine={false}
          unit="%"
          domain={[0, 25]}
        />
        <Tooltip {...tooltipStyle} />
        <Legend
          verticalAlign="top"
          align="left"
          height={28}
          wrapperStyle={{ fontSize: 13, color: HEX.muted }}
        />
        <Bar
          yAxisId="weight"
          dataKey="tonnes"
          name="Delivered"
          fill={HEX.forest600}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
        />
        <Line
          yAxisId="moisture"
          type="monotone"
          dataKey="moisture"
          name="Average moisture"
          stroke={HEX.wheat600}
          strokeWidth={2}
          dot={{ r: 2, fill: HEX.wheat600 }}
          connectNulls
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
