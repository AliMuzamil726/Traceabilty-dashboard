import { MoreHorizontal } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/core/utils/cn';
import { formatDate, formatDecimal, formatNumber } from '@/core/utils/format';
import { DataTable, EmptyState, type Column, type SortState } from '@/design-system/components';
import type { RadarRow } from '../api/types';
import { BUCKET_CLASSES, PICKUP_LABEL } from '../lib/status';
import { StatusPill } from './StatusPill';

export interface RadarTableProps {
  rows: RadarRow[];
  total: number;
  page: number;
  pageSize: number;
  unit: 'acre' | 'ha';
  sort: string;
  loading: boolean;
  selected: Set<string>;
  onSelectedChange: (selected: Set<string>) => void;
  onSortChange: (sort: string) => void;
  onPageChange: (page: number) => void;
  onViewOnMap: (row: RadarRow) => void;
  onRequest: (row: RadarRow) => void;
  onCancel: (row: RadarRow) => void;
}

interface MenuItem {
  label: string;
  onSelect: () => void;
  disabled?: boolean;
}

/** A small accessible action menu for one row. */
function RowMenu({ label, items }: { label: string; items: MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const dismiss = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', close);
    window.addEventListener('scroll', dismiss, true);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', close);
      window.removeEventListener('scroll', dismiss, true);
    };
  }, [open]);
  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          // Fixed position, so the table's horizontal scroll box cannot clip the menu.
          const box = e.currentTarget.getBoundingClientRect();
          const below = window.innerHeight - box.bottom > 200;
          setAt({ top: below ? box.bottom + 4 : box.top - 4 - 4 * 40, left: box.right - 192 });
          setOpen(!open);
        }}
        className="flex h-8 w-8 items-center justify-center rounded-control text-muted hover:bg-forest-50 hover:text-forest-800"
      >
        <MoreHorizontal className="h-4 w-4" aria-hidden />
      </button>
      {open && (
        <ul role="menu" style={{ top: at.top, left: at.left }} className="fixed z-40 w-48 rounded-control border border-line bg-surface p-1 shadow-2">
          {items.map((item) => (
            <li key={item.label} role="none">
              <button
                type="button"
                role="menuitem"
                disabled={item.disabled}
                onClick={(e) => {
                  e.stopPropagation();
                  setOpen(false);
                  item.onSelect();
                }}
                className="w-full rounded-sm px-3 py-2 text-left text-sm text-ink hover:bg-forest-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function toSortState(sort: string): SortState {
  return sort.startsWith('-') ? { key: sort.slice(1), direction: 'desc' } : { key: sort, direction: 'asc' };
}

export function RadarTable(props: RadarTableProps) {
  const { rows, total, page, pageSize, unit, sort, loading, selected, onSelectedChange, onSortChange, onPageChange } = props;
  const navigate = useNavigate();

  const columns: Column<RadarRow>[] = [
    { key: 'sawie_id', header: 'SAWIE ID', sortable: true, mono: true, cell: (r) => r.sawie_id },
    { key: 'farmer', header: 'Farmer', sortable: true, cell: (r) => <span className="font-medium">{r.farmer_name}</span> },
    { key: 'father_or_farm', header: unit === 'acre' ? 'Father' : 'Farm', cell: (r) => r.father_or_farm ?? '-' },
    { key: 'location', header: 'Location', sortable: true, cell: (r) => r.location },
    { key: 'officer', header: 'Officer', sortable: true, cell: (r) => r.officer_name ?? '-' },
    { key: 'field_id', header: 'Field ID', sortable: true, mono: true, cell: (r) => r.field_code },
    {
      key: 'area',
      header: `Area (${unit === 'acre' ? 'acres' : 'ha'})`,
      sortable: true,
      numeric: true,
      // One unit per programme: a second unit in every row made the column read as two
      // numbers and invited comparisons in the wrong one.
      cell: (r) => formatDecimal(unit === 'acre' ? r.area_acre : r.area_ha),
    },
    { key: 'sowing_date', header: 'Sowing date', sortable: true, cell: (r) => (r.sowing_date ? formatDate(r.sowing_date) : '-') },
    {
      key: 'das',
      header: 'Days after sowing',
      sortable: true,
      cell: (r) =>
        r.days_after_sowing === null ? (
          '-'
        ) : (
          <span className="flex min-w-[96px] items-center gap-2">
            <span className="tabular w-8 text-right">{r.days_after_sowing}</span>
            <span className="h-1.5 flex-1 rounded-full bg-canvas" role="img" aria-label={`${Math.round((r.progress ?? 0) * 100)} percent of the season`}>
              <span className={cn('block h-full rounded-full', BUCKET_CLASSES[r.status].dot)} style={{ width: `${(r.progress ?? 0) * 100}%` }} />
            </span>
          </span>
        ),
    },
    { key: 'status', header: 'Status', sortable: true, cell: (r) => <StatusPill status={r.status} overdue={r.overdue} /> },
    { key: 'expected_ready', header: 'Expected ready', sortable: true, cell: (r) => (r.expected_ready ? formatDate(r.expected_ready) : '-') },
    {
      key: 'pickup',
      header: 'Pickup',
      sortable: true,
      cell: (r) => (
        <span className="whitespace-nowrap">
          {PICKUP_LABEL[r.pickup_state]}
          {r.request_no && <span className="ml-1 font-mono text-xs text-muted">{r.request_no}</span>}
        </span>
      ),
    },
    {
      key: 'next_milestone',
      header: 'Next milestone',
      cell: (r) => (
        <span className="whitespace-nowrap">
          {r.next_milestone}
          {r.estimated_kg ? (
            <span className="block text-xs text-muted">
              {r.estimate_is_benchmark ? 'Estimate ' : ''}
              {formatNumber(r.estimated_kg)} kg
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: 'menu',
      header: 'Actions',
      cell: (r) => (
        <RowMenu
          label={`Actions for field ${r.field_code}`}
          items={[
            {
              label: 'Open fieldbook',
              onSelect: () => navigate(`/fieldbook?farmerId=${r.farmer_id}&fieldId=${r.field_id}`),
            },
            { label: 'View on map', onSelect: () => props.onViewOnMap(r) },
            { label: 'Request pickup', disabled: !r.can_request, onSelect: () => props.onRequest(r) },
            { label: 'Cancel request', disabled: !(r.can_act && r.pickup_state === 'requested'), onSelect: () => props.onCancel(r) },
          ]}
        />
      ),
    },
  ];

  return (
    <DataTable
      caption="Fields on the harvest radar"
      columns={columns}
      rows={rows}
      rowKey={(r) => r.field_id}
      loading={loading}
      sort={toSortState(sort)}
      onSortChange={(s) => onSortChange(s ? (s.direction === 'desc' ? `-${s.key}` : s.key) : 'expected_ready')}
      pagination={{ page, pageSize, total, onPageChange }}
      selectable
      selected={selected}
      onSelectedChange={onSelectedChange}
      empty={<EmptyState compact title="No fields match" description="Change or clear the filters to see more fields." />}
    />
  );
}
