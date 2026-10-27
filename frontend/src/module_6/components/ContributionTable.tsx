import { formatNumber } from '@/core/utils/format';
import { EmptyState } from '@/design-system/components';
import type { Contribution } from '../api/types';

/** Each farmer's share of the input, largest first. */
export function ContributionTable({ rows }: { rows: Contribution[] }) {
  if (!rows.length) return <EmptyState compact title="No contributions yet" />;
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">Farmer contribution</caption>
      <thead>
        <tr className="border-b border-line text-left text-muted">
          <th scope="col" className="py-2 font-medium">Farmer</th>
          <th scope="col" className="py-2 text-right font-medium">Deliveries</th>
          <th scope="col" className="py-2 text-right font-medium">Fields</th>
          <th scope="col" className="py-2 text-right font-medium">kg</th>
          <th scope="col" className="w-1/3 py-2 font-medium">Share</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.farmer_id} className="border-b border-line last:border-0">
            <td className="py-2">{r.farmer_name ?? '-'} <span className="font-mono text-xs text-muted">{r.sawie_id}</span></td>
            <td className="tabular py-2 text-right">{r.deliveries}</td>
            <td className="tabular py-2 text-right">{r.fields}</td>
            <td className="tabular py-2 text-right">{formatNumber(Number(r.kg))}</td>
            <td className="py-2">
              <span className="flex items-center gap-2">
                <span className="h-2 flex-1 rounded-full bg-canvas"><span className="block h-full rounded-full bg-forest-500" style={{ width: `${Number(r.pct)}%` }} /></span>
                <span className="tabular w-14 text-right">{r.pct}%</span>
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
