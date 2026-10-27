import { formatDate, formatDateTime, formatNumber } from '@/core/utils/format';
import { Badge, Card, EmptyState, KeyValueList, SectionHeader, StatCard } from '@/design-system/components';
import type { LotOverview as Overview } from '../api/types';
import { QrCard } from './QrCard';

/** The lot's own code, a short summary and how often its codes were scanned. */
export function LotOverview({ lot }: { lot: Overview }) {
  return (
    <Card as="section" aria-label={`${lot.kind} ${lot.heap_id}`} padding="lg" className="flex flex-col gap-5">
      <SectionHeader title={<span className="mono-id">{lot.heap_id}</span>}
        description={`${lot.kind} at ${lot.site_name ?? 'unknown site'}`}
        actions={<Badge tone={lot.status === 'open' ? 'info' : 'success'}>{lot.status === 'open' ? 'Open' : 'Closed'}</Badge>} />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[auto_minmax(0,1fr)]">
        {lot.token && lot.trace_url
          ? <QrCard token={lot.token} url={lot.trace_url} name={lot.heap_id} />
          : <EmptyState compact title="No code for this lot" description="Codes are made when a lot is opened." />}
        <KeyValueList columns={2} items={[
          { label: 'Opened', value: formatDate(lot.opened_at) },
          { label: 'Closed', value: lot.closed_at ? formatDate(lot.closed_at) : 'Still open' },
          { label: 'Input', value: `${formatNumber(lot.input_kg)} kg` },
          { label: 'Expected output', value: `${formatNumber(lot.expected_output_kg)} kg (${lot.outturn_ratio_pct}%)` },
          { label: 'Bales', value: `${lot.bales_made} of ${lot.max_bales}` },
        ]} />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label="Scans" value={formatNumber(lot.scans_total)} />
        <StatCard label="Public scans" value={formatNumber(lot.scans_public)} />
        <StatCard label="Last scan" value={lot.last_scan_at ? formatDateTime(lot.last_scan_at) : 'None yet'} />
      </div>
    </Card>
  );
}
