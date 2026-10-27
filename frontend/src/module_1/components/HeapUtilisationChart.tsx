import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Distribution } from '../api/types';
import { HEX, tonnes } from '../lib/format';
import { axisStyle, gridStyle, tooltipStyle } from '../lib/charts';

/**
 * What went into each heap, what should come out, and what has been baled so far.
 * The three bars together say whether a heap is keeping up with its input.
 */
export default function HeapUtilisationChart({ data }: { data: Distribution }) {
  const rows = data.heap_utilisation.map((heap) => ({
    label: heap.heap_id,
    input: tonnes(heap.input_kg),
    expected: tonnes(heap.expected_output_kg),
    baled: tonnes(heap.bales_made * safeUnit(heap)),
    bales: heap.bales_made,
    max: heap.max_bales,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} {...gridStyle} />
        <XAxis dataKey="label" {...axisStyle} tick={{ ...axisStyle.tick, fontSize: 10 }} interval="preserveStartEnd" angle={-35} textAnchor="end" height={64} />
        <YAxis {...axisStyle} axisLine={false} unit=" t" />
        <Tooltip
          {...tooltipStyle}
          formatter={(value: number, name) => [`${value} t`, String(name)]}
          labelFormatter={(label: string) => {
            const row = rows.find((r) => r.label === label);
            return row ? `${label}: ${row.bales} of ${row.max} bales` : label;
          }}
        />
        <Legend
          verticalAlign="top"
          align="left"
          height={28}
          wrapperStyle={{ fontSize: 13, color: HEX.muted }}
        />
        <Bar dataKey="input" name="Input" fill={HEX.forest700} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        <Bar dataKey="expected" name="Expected output" fill={HEX.forest500} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        <Bar dataKey="baled" name="Baled" fill={HEX.wheat500} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Bale weight per heap, worked back from the expected output and the bale limit. */
function safeUnit(heap: Distribution['heap_utilisation'][number]): number {
  if (heap.max_bales <= 0) return 0;
  return heap.expected_output_kg / heap.max_bales;
}
