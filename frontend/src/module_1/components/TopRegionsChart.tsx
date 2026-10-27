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

/** The districts (cotton) or counties (hemp) with the most mapped area. */
export default function TopRegionsChart({ data }: { data: Distribution }) {
  const rows = data.top_regions.map((region) => ({
    label: region.region,
    area: region.area,
    fields: region.fields,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid horizontal={false} {...gridStyle} />
        <XAxis type="number" {...axisStyle} axisLine={false} unit={` ${data.area_unit}`} />
        <YAxis type="category" dataKey="label" width={116} {...axisStyle} />
        <Tooltip
          {...tooltipStyle}
          formatter={(value: number, _name, item) => [
            `${value} ${data.area_unit} across ${(item.payload as { fields: number }).fields} fields`,
            'Mapped',
          ]}
        />
        <Bar
          dataKey="area"
          name="Mapped area"
          fill={HEX.wheat600}
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
