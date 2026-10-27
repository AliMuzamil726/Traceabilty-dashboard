import { cn } from '@/core/utils/cn';
import type { Bucket } from '../api/types';
import { BUCKET_CLASSES, BUCKET_LABEL, BUCKET_ORDER } from '../lib/status';

export interface BucketBarProps {
  counts: Record<Bucket, number> | undefined;
  active: Bucket | '';
  onChange: (bucket: Bucket | '') => void;
}

/** Clickable bucket cards. Clicking the active one again shows every bucket. */
export function BucketBar({ counts, active, onChange }: BucketBarProps) {
  return (
    <div role="group" aria-label="Filter by status" className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
      {BUCKET_ORDER.map((bucket) => {
        const on = active === bucket;
        return (
          <button
            key={bucket}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? '' : bucket)}
            className={cn(
              'flex items-center justify-between gap-2 rounded-card border bg-surface px-4 py-3 text-left transition-colors',
              on ? 'border-forest-700 ring-2 ring-forest-700' : 'border-line hover:border-forest-500',
            )}
          >
            <span className="flex items-center gap-2 text-sm font-medium text-ink">
              <span className={cn('h-2.5 w-2.5 rounded-full', BUCKET_CLASSES[bucket].dot)} aria-hidden />
              {BUCKET_LABEL[bucket]}
            </span>
            <span className="tabular text-lg font-semibold text-ink">{counts ? counts[bucket] : '-'}</span>
          </button>
        );
      })}
    </div>
  );
}
