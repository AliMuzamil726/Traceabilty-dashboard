import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { CartesianGrid } from 'recharts';
import type { Distribution } from '../api/types';
import { BUCKET_HEX, HEX } from '../lib/format';
import { axisStyle, gridStyle, tooltipStyle } from '../lib/charts';

/** How the season's fields are spread across the readiness buckets. */
export default function ReadinessChart({ data }: { data: Distribution }) {
  const rows = data.readiness.map((slice) => ({
    label: slice.label,
    bucket: slice.bucket,
    fields: slice.fields,
    area: slice.area,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} {...gridStyle} />
        <XAxis dataKey="label" {...axisStyle} tick={{ ...axisStyle.tick, fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={52} />
        <YAxis allowDecimals={false} {...axisStyle} axisLine={false} />
        <Tooltip
          {...tooltipStyle}
          formatter={(value: number, _name, item) => [
            `${value} fields, ${(item.payload as { area: number }).area} ${data.area_unit}`,
            'Fields',
          ]}
        />
        <Bar dataKey="fields" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {rows.map((row) => (
            <Cell
              key={row.bucket}
              fill={BUCKET_HEX[row.bucket]}
              stroke={row.bucket === 'no_sowing_data' ? HEX.muted : undefined}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
