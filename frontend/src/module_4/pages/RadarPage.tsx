import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { Button, EmptyState, PageHeader, Select, Tabs, toast } from '@/design-system/components';
import { radarApi, radarKeys } from '../api/client';
import type { RadarRow } from '../api/types';
import { BucketBar } from '../components/BucketBar';
import { CropSegment } from '../components/CropSegment';
import { DemandChart } from '../components/DemandChart';
import { KpiStrip } from '../components/KpiStrip';
import { CancelRequestDialog, type CancelTarget } from '../components/PickupRequestsPanel';
import { RadarCalendar } from '../components/RadarCalendar';
import { RadarFilters } from '../components/RadarFilters';
import { RadarMap } from '../components/RadarMap';
import { RadarTable } from '../components/RadarTable';
import { RequestPickupDialog } from '../components/RequestPickupDialog';
import { SelectionBar } from '../components/SelectionBar';
import { useRadarFilters, type RadarView } from '../hooks/useRadarFilters';
import { PAGE_SIZE, useRadarCalendar, useRadarFields, useRadarMap } from '../hooks/useRadarQuery';
import { requestBlockers } from '../lib/selection';

const VIEWS: { value: RadarView; label: string }[] = [
  { value: 'table', label: 'Table' },
  { value: 'map', label: 'Map' },
  { value: 'calendar', label: 'Calendar' },
];

function seasonOptions(): { value: string; label: string }[] {
  const now = new Date().getFullYear();
  return [now + 1, now, now - 1, now - 2].map((y) => ({ value: String(y), label: String(y) }));
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Harvest Radar: which fields are growing, approaching, ready, harvested or overdue, and
 * which already have a pickup requested. Every view reads the same URL filters.
 */
export default function RadarPage() {
  const { filters: f, apiParams, update, clear } = useRadarFilters();
  const client = useQueryClient();
  const fields = useRadarFields(apiParams, f.sort, f.page);
  const map = useRadarMap(apiParams, f.view === 'map');
  const calendar = useRadarCalendar(apiParams, f.month, f.view === 'calendar');

  // Selection survives paging, so it keeps the rows it was made from.
  const [selected, setSelected] = useState<Map<string, RadarRow>>(new Map());
  const [requestRows, setRequestRows] = useState<RadarRow[] | null>(null);
  const [cancelTarget, setCancelTarget] = useState<CancelTarget | null>(null);
  const [focusFieldId, setFocusFieldId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => setSelected(new Map()), [f.crop, f.season]);

  const data = fields.data;
  const unit = data?.area_unit ?? (f.crop === 'cotton' ? 'acre' : 'ha');
  const selectedRows = useMemo(() => [...selected.values()], [selected]);
  const blockers = useMemo(() => requestBlockers(selectedRows), [selectedRows]);

  const onSelectedChange = (keys: Set<string>) => {
    const next = new Map<string, RadarRow>();
    const onPage = new Map((data?.items ?? []).map((r) => [r.field_id, r]));
    for (const key of keys) {
      const row = selected.get(key) ?? onPage.get(key);
      if (row) next.set(key, row);
    }
    setSelected(next);
  };

  const refresh = () => client.invalidateQueries({ queryKey: radarKeys.all });

  const exportCsv = async () => {
    setExporting(true);
    try {
      const ids = selectedRows.map((r) => r.field_id).join(',');
      const { blob, filename } = await radarApi.exportCsv({ ...apiParams, sort: f.sort, field_ids: ids || undefined });
      download(blob, filename);
    } catch (e) {
      toast.error('The export failed', toApiError(e).message);
    } finally {
      setExporting(false);
    }
  };

  const requestFromMap = useCallback(
    (fieldId: string) => {
      const row = data?.items.find((r) => r.field_id === fieldId) ?? selected.get(fieldId);
      if (row) {
        setRequestRows([row]);
        return;
      }
      // Not on the current table page: fetch just that field with the same filters.
      radarApi
        .fields({ ...apiParams, field_ids: fieldId, page_size: 1 })
        .then((page) => page.items[0] && setRequestRows([page.items[0]]))
        .catch((e: unknown) => toast.error('That field could not be loaded', toApiError(e).message));
    },
    [data, selected, apiParams],
  );

  const selectedDay = f.from && f.from === f.to ? f.from : null;

  return (
    <div className="flex flex-col gap-5 pb-24">
      <PageHeader
        title="Harvest Radar"
        subtitle="Which fields are ready, which are coming, and which already have a pickup requested."
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <CropSegment value={f.crop} onChange={(crop) => update({ crop })} />
            <div className="w-28">
              <Select aria-label="Season" value={String(f.season)} options={seasonOptions()} onChange={(e) => update({ season: e.target.value })} />
            </div>
          </div>
        }
      />

      {fields.error && !data ? (
        <EmptyState title="The radar could not be loaded" description={toApiError(fields.error).message} action={<Button onClick={() => void refresh()}>Try again</Button>} />
      ) : (
        <>
          <KpiStrip kpis={data?.kpis} unit={unit} loading={fields.isLoading} />
          <BucketBar counts={data?.buckets} active={f.status} onChange={(status) => update({ status })} />
          <RadarFilters filters={f} facets={data?.facets} isAdmin={data?.is_admin ?? false} onChange={update} onClear={clear} />

          <Tabs aria-label="Radar views" value={f.view} onChange={(view) => update({ view })} items={VIEWS.map((v) => (v.value === 'table' ? { ...v, count: data?.total } : v))}>
            {(view) => (
              <div className="mt-4">
                {view === 'table' && (
                  <RadarTable
                    rows={data?.items ?? []}
                    total={data?.total ?? 0}
                    page={f.page}
                    pageSize={PAGE_SIZE}
                    unit={unit}
                    sort={f.sort}
                    loading={fields.isLoading}
                    selected={new Set(selected.keys())}
                    onSelectedChange={onSelectedChange}
                    onSortChange={(sort) => update({ sort })}
                    onPageChange={(page) => update({ page })}
                    onViewOnMap={(row) => {
                      setFocusFieldId(row.field_id);
                      update({ view: 'map' });
                    }}
                    onRequest={(row) => setRequestRows([row])}
                    onCancel={(row) => row.request_id && setCancelTarget({ id: row.request_id, request_no: row.request_no ?? 'request', field_code: row.field_code })}
                  />
                )}
                {view === 'map' && <RadarMap crop={f.crop} data={map.data} loading={map.isLoading} focusFieldId={focusFieldId} onRequest={requestFromMap} />}
                {view === 'calendar' && (
                  <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
                    <RadarCalendar
                      month={f.month}
                      data={calendar.data}
                      loading={calendar.isLoading}
                      selectedDay={selectedDay}
                      onMonthChange={(month) => update({ month })}
                      onPickDay={(day) => update({ from: day, to: day, view: 'table' })}
                    />
                    <DemandChart weeks={calendar.data?.weeks} />
                  </div>
                )}
              </div>
            )}
          </Tabs>
        </>
      )}

      <SelectionBar
        count={selected.size}
        blockers={blockers}
        exporting={exporting}
        onRequest={() => setRequestRows(selectedRows)}
        onExport={() => void exportCsv()}
        onClear={() => setSelected(new Map())}
      />
      {selected.size === 0 && f.view === 'table' && data && data.total > 0 && (
        <div className="flex justify-end">
          <Button variant="secondary" size="sm" loading={exporting} onClick={() => void exportCsv()}>
            Export CSV of all {data.total} filtered fields
          </Button>
        </div>
      )}

      <RequestPickupDialog
        open={requestRows !== null}
        rows={requestRows ?? []}
        crop={f.crop}
        season={f.season}
        unit={unit}
        onClose={() => setRequestRows(null)}
        onDone={() => setSelected(new Map())}
      />
      <CancelRequestDialog target={cancelTarget} onClose={() => setCancelTarget(null)} />
    </div>
  );
}
