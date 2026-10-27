import type { ReactNode } from 'react';
import { cn } from '@/core/utils/cn';
import { Skeleton } from './Skeleton';

export interface StatCardProps {
  label: string;
  value?: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  loading?: boolean;
  className?: string;
}

/**
 * KPI tile. The label, value and hint always stack from the top, so the values in a
 * row of tiles share a baseline whether or not a tile has a hint. With `loading` it
 * renders its skeleton state.
 *
 * Layout: min-w-0 + break-words so long labels/hints never overflow the card.
 */
export function StatCard({ label, value, hint, icon, loading = false, className }: StatCardProps) {
  return (
    <div
      className={cn(
        'flex min-h-[112px] min-w-0 flex-col gap-2 rounded-card border border-line bg-surface p-4 shadow-1 transition-shadow duration-base hover:shadow-2',
        className,
      )}
      aria-busy={loading || undefined}
    >
      <div className="flex min-w-0 items-start justify-between gap-2">
        {loading ? (
          <Skeleton className="w-28" />
        ) : (
          <span className="min-w-0 flex-1 text-sm font-medium leading-snug text-muted break-words">
            {label}
          </span>
        )}
        {icon && (
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-forest-50 text-forest-700 [&>svg]:h-4 [&>svg]:w-4"
            aria-hidden
          >
            {icon}
          </span>
        )}
      </div>
      {loading ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-6 w-20" shape="block" />
          <Skeleton className="w-36" />
          <span className="sr-only">Loading {label}</span>
        </div>
      ) : (
        <div className="min-w-0">
          <div className="break-words tabular-nums text-2xl font-semibold tracking-[-0.02em] text-ink">
            {value}
          </div>
          {hint && (
            <div className="mt-1 break-words text-sm leading-snug text-muted">{hint}</div>
          )}
        </div>
      )}
    </div>
  );
}
