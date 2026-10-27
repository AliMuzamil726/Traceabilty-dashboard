import { TriangleAlert } from 'lucide-react';
import { formatDecimal, formatNumber } from '@/core/utils/format';
import type { GeometryValidation } from '../api/types';

export interface OverlapAlertProps {
  validation: GeometryValidation | null;
  checking?: boolean;
}

/**
 * Why the Save button is disabled.
 *
 * Fields may touch but must not overlap, so a conflict names the other field, its
 * farmer and how much ground is shared. Showing the share as well as the area matters:
 * "4 m2" sounds like nothing until it is also "0.01 percent of this field", which tells
 * the officer they have a sliver to nudge rather than a boundary to redraw.
 *
 * This is one of the three places the error red is allowed, per DESIGN_SYSTEM.md.
 */
export function OverlapAlert({ validation, checking }: OverlapAlertProps) {
  if (checking || !validation || validation.valid) return null;

  const { conflicts, message, error_code: code } = validation;

  if (conflicts.length === 0) {
    return (
      <div
        role="alert"
        className="flex items-start gap-3 rounded-card border border-danger bg-danger-tint p-4"
      >
        <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden />
        <div>
          <p className="font-medium text-ink">This boundary cannot be saved</p>
          <p className="mt-0.5 text-base text-muted">
            {message ?? 'Check the shape and try again.'}
          </p>
          {code && <p className="mono-id mt-1 text-xs text-muted">{code}</p>}
        </div>
      </div>
    );
  }

  return (
    <div
      role="alert"
      className="rounded-card border border-danger bg-danger-tint p-4"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink">
            This boundary overlaps {conflicts.length} existing field
            {conflicts.length === 1 ? '' : 's'}
          </p>
          <p className="mt-0.5 text-base text-muted">
            Fields may touch along a shared boundary, but they must not overlap. Adjust the
            corners until the overlap is gone.
          </p>
          <ul className="mt-3 flex flex-col gap-2">
            {conflicts.map((conflict) => (
              <li
                key={conflict.field_id}
                className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-t border-danger/20 pt-2 text-base first:border-t-0 first:pt-0"
              >
                <span className="mono-id font-medium text-ink">{conflict.field_code}</span>
                <span className="text-muted">
                  {conflict.farmer_name}, SAWIE ID{' '}
                  <span className="mono-id">{conflict.sawie_id}</span>
                </span>
                <span className="tabular ml-auto text-ink">
                  {formatNumber(conflict.overlap_m2, 0)} m&sup2;
                  <span className="ml-1 text-muted">
                    ({formatDecimal(conflict.overlap_percent_of_new_field, 2)}% of this field)
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
