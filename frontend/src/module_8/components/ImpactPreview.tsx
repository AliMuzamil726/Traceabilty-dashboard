import { ArrowRight, Info } from 'lucide-react';
import { Badge } from '@/design-system/components/Badge';
import { Skeleton } from '@/design-system/components/Skeleton';
import type { ClockPreview } from '../api/types';

export interface ImpactPreviewProps {
  preview: ClockPreview | undefined;
  loading: boolean;
}

/**
 * What a crop-clock change would do, before it is saved.
 *
 * Moving the ready day moves fields between Growing, Approaching, Ready and Overdue on
 * Harvest Radar, which decides whose crop an officer goes to collect. The counts make
 * that visible while the change can still be reconsidered.
 */
export function ImpactPreview({ preview, loading }: ImpactPreviewProps) {
  if (loading) return <Skeleton className="h-24 w-full" shape="block" />;
  if (!preview) return null;

  if (preview.fields_examined === 0) {
    return (
      <p className="flex items-start gap-2 rounded-control bg-forest-50 px-3 py-2 text-sm text-ink">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-forest-700" aria-hidden />
        No field has a sowing date this season yet, so this change moves nothing today.
      </p>
    );
  }

  return (
    <div className="rounded-control bg-forest-50 px-3 py-2">
      <p className="text-sm text-ink">
        Of {preview.fields_examined} field{preview.fields_examined === 1 ? '' : 's'} with a sowing
        date,{' '}
        <strong className="font-medium">
          {preview.fields_moving} would change bucket
        </strong>{' '}
        the moment this is saved.
      </p>
      {preview.moves.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {preview.moves.map((move) => (
            <li key={`${move.from}-${move.to}`}>
              <Badge tone="neutral">
                <span className="flex items-center gap-1">
                  {move.from}
                  <ArrowRight className="h-3 w-3" aria-label="to" />
                  {move.to}: {move.fields}
                </span>
              </Badge>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-muted">
        Records already made do not change. Only what the radar shows from now on does.
      </p>
    </div>
  );
}
