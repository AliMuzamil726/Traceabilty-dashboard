/**
 * The look of every chart, in one place.
 *
 * Recharts takes colours as strings, so the brand tokens are repeated as hex in
 * `format.ts` and used from here. Nothing in a chart animates on a loop: a series is
 * drawn once and then stands still.
 */
import { HEX } from './format';

export const gridStyle = { stroke: HEX.line } as const;

export const axisStyle = {
  tickLine: false,
  axisLine: { stroke: HEX.line },
  tick: { fill: HEX.muted, fontSize: 12 },
} as const;

export const tooltipStyle = {
  cursor: { fill: HEX.wheat300, fillOpacity: 0.25 },
  contentStyle: {
    borderColor: HEX.line,
    borderRadius: 10,
    fontSize: 13,
    color: HEX.ink,
    boxShadow: '0 1px 2px rgb(21 34 27 / 0.06), 0 8px 24px rgb(21 34 27 / 0.08)',
  },
  labelStyle: { color: HEX.muted, marginBottom: 2 },
} as const;

/** The draw-once animation chart series use, so a redraw is not a light show. */
export const DRAW = { isAnimationActive: false } as const;
