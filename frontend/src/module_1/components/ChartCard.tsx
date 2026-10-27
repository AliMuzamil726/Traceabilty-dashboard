import { Table2 } from 'lucide-react';
import { Suspense, useId, useState, type ReactNode } from 'react';
import { cn } from '@/core/utils/cn';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { EmptyState } from '@/design-system/components/EmptyState';
import { Skeleton } from '@/design-system/components/Skeleton';
import { SectionError } from './SectionCard';

export interface ChartDataColumn {
  header: string;
  numeric?: boolean;
}

export interface ChartCardProps {
  title: ReactNode;
  description?: ReactNode;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  /** True when there is nothing to draw yet. */
  empty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  height?: string;
  /** Column headers of the table behind the chart. */
  columns: ChartDataColumn[];
  /** The same numbers the chart draws, one array per row. */
  rows: (string | number)[][];
  children: ReactNode;
  className?: string;
}

/**
 * A chart with the numbers behind it.
 *
 * Every chart carries a "Show data" toggle that reveals the same figures as a real
 * table. A picture of a trend is useless to a screen reader and awkward to quote in a
 * report, so the table is part of the chart rather than an alternative to it.
 */
export function ChartCard({
  title,
  description,
  loading = false,
  error,
  onRetry,
  empty = false,
  emptyTitle = 'Nothing to chart yet',
  emptyDescription = 'Figures appear here as the season goes on.',
  height = 'h-64',
  columns,
  rows,
  children,
  className,
}: ChartCardProps) {
  const [showData, setShowData] = useState(false);
  const headingId = useId();
  const tableId = useId();

  return (
    <Card as="section" aria-labelledby={headingId} padding="md" className={cn('min-w-0', className)}>
      <SectionHeader
        id={headingId}
        title={title}
        description={description}
        as="h3"
        actions={
          !error && !empty ? (
            <Button
              variant="ghost"
              size="sm"
              className="-mr-2 -mt-1 text-muted"
              onClick={() => setShowData((open) => !open)}
              aria-expanded={showData}
              aria-controls={tableId}
              leftIcon={<Table2 className="h-4 w-4" aria-hidden />}
            >
              {showData ? 'Hide data' : 'Show data'}
            </Button>
          ) : undefined
        }
      />
      <div className="mt-4">
        {error ? (
          <SectionError error={error} onRetry={onRetry} />
        ) : loading ? (
          <Skeleton className={cn('w-full', height)} shape="block" />
        ) : empty ? (
          <EmptyState compact title={emptyTitle} description={emptyDescription} />
        ) : (
          <>
            <div className={cn('w-full', height)}>
              <Suspense fallback={<Skeleton className={cn('w-full', height)} shape="block" />}>
                {children}
              </Suspense>
            </div>
            <div id={tableId} hidden={!showData} className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <caption className="sr-only">The figures behind this chart</caption>
                <thead>
                  <tr className="border-b border-line">
                    {columns.map((column) => (
                      <th
                        key={column.header}
                        scope="col"
                        className={cn(
                          'py-2 pe-3 font-medium text-muted',
                          column.numeric ? 'text-right' : 'text-left',
                        )}
                      >
                        {column.header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, index) => (
                    <tr key={index} className="border-b border-line/60 last:border-0">
                      {row.map((cell, cellIndex) => (
                        <td
                          key={cellIndex}
                          className={cn(
                            'py-1.5 pe-3 text-ink',
                            columns[cellIndex]?.numeric && 'tabular text-right',
                          )}
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
