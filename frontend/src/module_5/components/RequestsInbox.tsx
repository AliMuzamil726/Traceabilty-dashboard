import { CalendarPlus } from 'lucide-react';
import { useState } from 'react';
import { formatDate, formatNumber } from '@/core/utils/format';
import { Button, DataTable, EmptyState, Tooltip, type Column } from '@/design-system/components';
import type { InboxItem } from '../api/types';
import { ScheduleDialog } from './ScheduleDialog';

/** Radar requests waiting for transport. Select one or many and schedule them together. */
export function RequestsInbox({ items, loading }: { items: InboxItem[]; loading: boolean }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState(false);
  const chosen = items.filter((i) => selected.has(i.request_id));
  const crops = new Set(chosen.map((i) => i.crop));
  const reasons = [
    ...(chosen.length === 0 ? ['Select at least one request.'] : []),
    ...(chosen.some((i) => !i.can_schedule) ? ["Some requests belong to another officer's farmers."] : []),
    ...(crops.size > 1 ? ['Schedule cotton and hemp separately: they go to different sites.'] : []),
  ];

  const columns: Column<InboxItem>[] = [
    { key: 'request_no', header: 'Request', mono: true, cell: (r) => r.request_no },
    { key: 'farmer', header: 'Farmer', cell: (r) => (r.farmer_name ? `${r.sawie_id}, ${r.farmer_name}` : '-') },
    { key: 'field', header: 'Field', mono: true, cell: (r) => r.field_code },
    { key: 'location', header: 'Location', cell: (r) => r.location },
    {
      key: 'estimate',
      header: 'Estimated quantity',
      numeric: true,
      cell: (r) => (r.estimated_quantity_kg === null ? '-' : `${r.quantity_is_estimate ? 'About ' : ''}${formatNumber(r.estimated_quantity_kg)} kg`),
    },
    { key: 'preferred', header: 'Preferred date', cell: (r) => (r.preferred_date ? formatDate(r.preferred_date) : '-') },
    { key: 'note', header: 'Note', cell: (r) => r.note ?? '-' },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted">{chosen.length ? `${chosen.length} selected` : 'Select requests to schedule a delivery for each.'}</p>
        <Tooltip disabled={reasons.length === 0} content={reasons.join(' ')}>
          <Button
            leftIcon={<CalendarPlus className="h-4 w-4" />}
            aria-disabled={reasons.length > 0 || undefined}
            className={reasons.length ? 'cursor-not-allowed opacity-50' : undefined}
            onClick={() => reasons.length === 0 && setOpen(true)}
          >
            Schedule
          </Button>
        </Tooltip>
      </div>
      <DataTable
        caption="Pickup requests waiting to be scheduled"
        columns={columns}
        rows={items}
        rowKey={(r) => r.request_id}
        loading={loading}
        selectable
        selected={selected}
        onSelectedChange={setSelected}
        empty={<EmptyState compact title="No requests waiting" description="Requests appear here when officers ask for a pickup in Harvest Radar." />}
      />
      <ScheduleDialog
        open={open}
        requests={chosen}
        onClose={() => setOpen(false)}
        onDone={() => setSelected(new Set())}
      />
    </div>
  );
}
