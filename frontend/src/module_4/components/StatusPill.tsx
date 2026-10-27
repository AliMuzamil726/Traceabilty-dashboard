import { cn } from '@/core/utils/cn';
import type { Bucket } from '../api/types';
import { BUCKET_CLASSES, BUCKET_LABEL } from '../lib/status';

/** A readiness bucket, with the overdue flag shown as a dashed Wheat badge beside it. */
export function StatusPill({ status, overdue = false }: { status: Bucket; overdue?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium', BUCKET_CLASSES[status].pill)}>
        {BUCKET_LABEL[status]}
      </span>
      {overdue && (
        <span className="inline-flex items-center rounded-full border border-dashed border-wheat-600 bg-wheat-50 px-2 py-0.5 text-xs font-medium text-ink">
          Overdue
        </span>
      )}
    </span>
  );
}
