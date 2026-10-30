import { useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { formatDate, formatDateTime, formatNumber } from '@/core/utils/format';
import { Badge, Card, DataTable, EmptyState, KeyValueList, Skeleton, Tabs, type Column } from '@/design-system/components';
import type { TraceDelivery } from '../api/types';
import { useTrace, type TraceTarget } from '../hooks/useTrace';
import { FarmerTraceCard } from './FarmerTraceCard';
import { FieldbookLog } from './FieldbookLog';
import { FieldTraceMap } from './FieldTraceMap';
import { VerificationPanel } from './VerificationPanel';

type Tab = 'bale' | 'heap' | 'deliveries' | 'farmers' | 'map' | 'log';

/** Drill down from a bale or lot to deliveries, farmers, fields and fieldbooks. */
export function TraceExplorer({ target }: { target: TraceTarget }) {
  const trace = useTrace(target);
  const [tab, setTab] = useState<Tab>(target.kind === 'bale' ? 'bale' : 'heap');
  const [field, setField] = useState<string | null>(null);
  if (trace.error) return <EmptyState title="This trace cannot be shown" description={toApiError(trace.error).message} />;
  const t = trace.data;
  if (!t) return <Skeleton className="h-72 w-full" shape="block" />;
  const focus = field ?? t.fields[0]?.field_id ?? null;
  const focusField = t.fields.find((f) => f.field_id === focus);
  const deliveryColumns: Column<TraceDelivery>[] = [
    { key: 'no', header: 'Delivery', mono: true, cell: (d) => d.delivery_no },
    { key: 'field', header: 'Field', mono: true, cell: (d) => d.field_code },
    { key: 'farmer', header: 'Farmer', cell: (d) => t.farmers.find((f) => f.farmer_id === d.farmer_id)?.name ?? '-' },
    { key: 'at', header: 'Delivered', cell: (d) => (d.delivered_at ? formatDateTime(d.delivered_at) : '-') },
    { key: 'wb', header: 'Weighbridge', numeric: true, cell: (d) => (d.weighbridge_weight_kg === null ? '-' : `${formatNumber(d.weighbridge_weight_kg)} kg`) },
    { key: 'moist', header: 'Moisture', numeric: true, cell: (d) => (d.moisture_pct === null ? '-' : `${d.moisture_pct}%`) },
    { key: 'status', header: 'Status', cell: (d) => <Badge size="sm" tone={d.status === 'delivered' ? 'success' : 'warning'}>{d.status.replace('_', ' ')}</Badge> },
  ];
  const items = [
    ...(t.bale ? [{ value: 'bale' as const, label: 'Bale' }] : []),
    { value: 'heap' as const, label: `${t.heap.kind} details` },
    { value: 'deliveries' as const, label: 'Deliveries', count: t.deliveries.length },
    { value: 'farmers' as const, label: 'Farmers', count: t.farmers.length },
    { value: 'map' as const, label: 'Field map', count: t.fields.length },
    { value: 'log' as const, label: 'Fieldbook log' },
  ];
  return (
    <Card as="section" aria-label="Trace" padding="lg" className="flex flex-col gap-4">
      <Tabs aria-label="Trace sections" value={tab} onChange={setTab} items={items} />
      {tab === 'bale' && t.bale && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <KeyValueList items={[
            { label: 'Serial', value: t.bale.serial, mono: true },
            { label: 'Weight', value: `${t.bale.weight_kg} kg` },
            { label: 'Status', value: t.bale.status === 'active' ? 'Active' : 'Voided' },
            { label: 'Produced', value: formatDateTime(t.bale.created_at) },
            { label: 'Code', value: t.token ?? 'None active', mono: true },
          ]} />
          <VerificationPanel checks={t.checks} />
        </div>
      )}
      {tab === 'heap' && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <KeyValueList items={[
            { label: t.heap.kind, value: t.heap.heap_id, mono: true },
            { label: 'Site', value: `${t.heap.site_name ?? '-'}${t.heap.site_code ? ` (${t.heap.site_code})` : ''}` },
            { label: 'Opened', value: formatDate(t.heap.opened_at) },
            { label: 'Closed', value: t.heap.closed_at ? formatDate(t.heap.closed_at) : 'Still open' },
            { label: 'Input', value: `${formatNumber(t.heap.input_kg)} kg` },
            { label: 'Expected output', value: `${formatNumber(t.heap.expected_output_kg)} kg (${t.heap.outturn_ratio_pct}%)` },
            { label: 'Bales', value: `${t.heap.bales_made} of ${t.heap.max_bales}` },
          ]} />
          <VerificationPanel checks={t.checks} />
        </div>
      )}
      {tab === 'deliveries' && (
        <DataTable caption="Deliveries in this lot" columns={deliveryColumns} rows={t.deliveries} rowKey={(d) => d.id}
          empty={<EmptyState compact title="No deliveries" />} />
      )}
      {tab === 'farmers' && (
        t.farmers.length
          ? <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">{t.farmers.map((f) => <FarmerTraceCard key={f.farmer_id} farmer={f} crop={t.heap.crop} />)}</div>
          : <EmptyState compact title="No farmers yet" />
      )}
      {(tab === 'map' || tab === 'log') && (
        <div className="flex flex-col gap-3">
          {t.fields.length > 1 && (
            <div role="group" aria-label="Field" className="flex flex-wrap gap-1.5">
              {t.fields.map((f) => (
                <button key={f.field_id} type="button" aria-pressed={focus === f.field_id} onClick={() => setField(f.field_id)}
                  className={`mono-id rounded-full border px-3 py-1 text-xs ${focus === f.field_id ? 'border-forest-700 bg-forest-700 text-white' : 'border-line bg-surface text-ink hover:border-forest-500'}`}>
                  {f.field_code}
                </button>
              ))}
            </div>
          )}
          {tab === 'map'
            ? <FieldTraceMap fields={t.fields} crop={t.heap.crop} focus={focus} onSelect={setField} />
            : focusField ? <FieldbookLog field={focusField} /> : <EmptyState compact title="No fields" />}
          {tab === 'map' && focusField && (
            <p className="text-xs text-muted">
              <span className="mono-id">{focusField.field_code}</span>
              {focusField.area_acre !== null &&
                (t.heap.crop === 'cotton'
                  ? `, ${formatNumber(focusField.area_acre, 2)} acres`
                  : `, ${formatNumber(focusField.area_ha ?? 0, 2)} ha`)}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
