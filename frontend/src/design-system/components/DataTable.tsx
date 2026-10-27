import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown } from 'lucide-react';
import { useEffect, useRef, type ReactNode } from 'react';
import { cn } from '@/core/utils/cn';
import { formatNumber } from '@/core/utils/format';
import { IconButton } from './IconButton';
import { Skeleton } from './Skeleton';

export type SortDirection = 'asc' | 'desc';

export interface SortState {
  key: string;
  direction: SortDirection;
}

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  sortable?: boolean;
  align?: 'left' | 'right' | 'center';
  /** Tabular numbers and right alignment. */
  numeric?: boolean;
  /** Monospace for IDs and coordinates. */
  nowrap?: boolean;
  mono?: boolean;
  width?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption: string;
  loading?: boolean;
  /** Rendered instead of the body when there are no rows. */
  empty?: ReactNode;
  sort?: SortState | null;
  onSortChange?: (sort: SortState | null) => void;
  /** Server-side pagination using the API Page contract. */
  pagination?: { page: number; pageSize: number; total: number; onPageChange: (page: number) => void };
  selectable?: boolean;
  selected?: Set<string>;
  onSelectedChange?: (selected: Set<string>) => void;
  onRowClick?: (row: T) => void;
  maxHeight?: string;
  className?: string;
}

function nextSort(current: SortState | null | undefined, key: string): SortState | null {
  if (!current || current.key !== key) return { key, direction: 'asc' };
  if (current.direction === 'asc') return { key, direction: 'desc' };
  return null;
}

function HeaderCheckbox({ checked, indeterminate, onChange }: { checked: boolean; indeterminate: boolean; onChange: () => void }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return <input ref={ref} type="checkbox" aria-label="Select all rows on this page" checked={checked} onChange={onChange} className="h-4 w-4 accent-forest-700" />;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  loading = false,
  empty,
  sort,
  onSortChange,
  pagination,
  selectable,
  selected = new Set<string>(),
  onSelectedChange,
  onRowClick,
  maxHeight = '70vh',
  className,
}: DataTableProps<T>) {
  const pageKeys = rows.map(rowKey);
  const selectedOnPage = pageKeys.filter((k) => selected.has(k)).length;
  const allSelected = pageKeys.length > 0 && selectedOnPage === pageKeys.length;

  const toggleAll = () => {
    const next = new Set(selected);
    if (allSelected) pageKeys.forEach((k) => next.delete(k));
    else pageKeys.forEach((k) => next.add(k));
    onSelectedChange?.(next);
  };
  const toggleOne = (key: string) => {
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onSelectedChange?.(next);
  };

  const colCount = columns.length + (selectable ? 1 : 0);
  const alignClass = (c: Column<T>) => (c.numeric || c.align === 'right' ? 'text-right' : c.align === 'center' ? 'text-center' : 'text-left');

  const pageCount = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.pageSize)) : 1;
  const from = pagination && pagination.total > 0 ? (pagination.page - 1) * pagination.pageSize + 1 : 0;
  const to = pagination ? Math.min(pagination.total, pagination.page * pagination.pageSize) : 0;

  return (
    <div className={cn('overflow-hidden rounded-card border border-line bg-surface shadow-1', className)}>
      <div className="overflow-auto" style={{ maxHeight }}>
        <table className="w-full border-collapse text-base" aria-busy={loading || undefined}>
          <caption className="sr-only">{caption}</caption>
          <thead className="sticky top-0 z-10 bg-canvas/95 backdrop-blur-sm">
            <tr className="border-b border-line">
              {selectable && (
                <th scope="col" className="w-10 px-4 py-3">
                  <HeaderCheckbox checked={allSelected} indeterminate={selectedOnPage > 0 && !allSelected} onChange={toggleAll} />
                </th>
              )}
              {columns.map((c) => {
                const active = sort?.key === c.key;
                const ariaSort = active ? (sort?.direction === 'asc' ? 'ascending' : 'descending') : undefined;
                return (
                  <th key={c.key} scope="col" aria-sort={ariaSort} style={{ width: c.width }} className={cn('whitespace-nowrap px-4 py-3 text-sm font-medium text-muted', alignClass(c))}>
                    {c.sortable && onSortChange ? (
                      <button
                        type="button"
                        onClick={() => onSortChange(nextSort(sort, c.key))}
                        className={cn('inline-flex items-center gap-1 rounded-sm hover:text-ink', active && 'text-ink', (c.numeric || c.align === 'right') && 'flex-row-reverse')}
                      >
                        {c.header}
                        {active ? (
                          sort?.direction === 'asc' ? <ArrowUp className="h-3.5 w-3.5" aria-hidden /> : <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                        ) : (
                          <ChevronsUpDown className="h-3.5 w-3.5 opacity-60" aria-hidden />
                        )}
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: 5 }, (_, i) => (
                <tr key={`sk-${i}`} className="border-b border-line last:border-b-0">
                  {Array.from({ length: colCount }, (__, j) => (
                    <td key={j} className="px-4 py-3.5">
                      <Skeleton className={j === 0 ? 'w-24' : 'w-full max-w-[160px]'} />
                    </td>
                  ))}
                </tr>
              ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={colCount}>{empty ?? <p className="px-4 py-10 text-center text-muted">Nothing to show yet.</p>}</td>
              </tr>
            )}
            {!loading &&
              rows.map((row) => {
                const key = rowKey(row);
                const isSelected = selected.has(key);
                return (
                  <tr
                    key={key}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={cn(
                      'border-b border-line transition-colors duration-fast last:border-b-0 hover:bg-forest-50/40',
                      onRowClick && 'cursor-pointer hover:bg-forest-50/60',
                      isSelected && 'bg-forest-50',
                    )}
                  >
                    {selectable && (
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          aria-label={`Select row ${key}`}
                          checked={isSelected}
                          onClick={(e) => e.stopPropagation()}
                          onChange={() => toggleOne(key)}
                          className="h-4 w-4 accent-forest-700"
                        />
                      </td>
                    )}
                    {columns.map((c) => (
                      <td key={c.key} className={cn('max-w-[28rem] px-4 py-3 text-ink', alignClass(c), c.numeric && 'tabular-nums', c.mono && 'mono-id text-sm', (c.mono || c.numeric || c.nowrap) ? 'whitespace-nowrap' : 'break-words')}>
                        {c.cell(row)}
                      </td>
                    ))}
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
      {pagination && (
        <div className="flex items-center justify-between gap-3 border-t border-line bg-canvas/50 px-4 py-2.5 text-sm text-muted">
          <span className="tabular">
            {pagination.total === 0 ? 'No results' : `${formatNumber(from)} to ${formatNumber(to)} of ${formatNumber(pagination.total)}`}
          </span>
          <div className="flex items-center gap-1">
            <span className="tabular mr-2">
              Page {pagination.page} of {pageCount}
            </span>
            <IconButton size="sm" label="Previous page" icon={<ChevronLeft className="h-4 w-4" />} disabled={pagination.page <= 1} onClick={() => pagination.onPageChange(pagination.page - 1)} />
            <IconButton size="sm" label="Next page" icon={<ChevronRight className="h-4 w-4" />} disabled={pagination.page >= pageCount} onClick={() => pagination.onPageChange(pagination.page + 1)} />
          </div>
        </div>
      )}
    </div>
  );
}
