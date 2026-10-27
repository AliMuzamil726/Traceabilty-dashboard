import { Loader2 } from 'lucide-react';
import { cn } from '@/core/utils/cn';

export interface SawieIdChipProps {
  sawieId: number | null;
  /** A preview is the number this farmer would probably get, not a promise. */
  preview?: boolean;
  loading?: boolean;
  size?: 'md' | 'lg';
  className?: string;
}

/**
 * The SAWIE ID, shown directly under the ID number field as soon as the lookup answers.
 *
 * A preview carries the hint "Assigned on save" on purpose: the real number is
 * allocated inside the saving transaction, so if another officer saves first this one
 * will differ. Promising the preview and then showing a different number on the success
 * screen would be worse than never promising it.
 */
export function SawieIdChip({
  sawieId,
  preview = false,
  loading = false,
  size = 'md',
  className,
}: SawieIdChipProps) {
  if (loading) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-2 rounded-pill border border-line bg-canvas px-3 py-1 text-sm text-muted',
          className,
        )}
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        Checking the ID number
      </span>
    );
  }

  if (sawieId === null) return null;

  return (
    <span
      className={cn(
        'inline-flex items-baseline gap-2 rounded-pill border px-3 py-1',
        preview ? 'border-line bg-canvas' : 'border-wheat-300/60 bg-wheat-100',
        className,
      )}
    >
      <span className={cn('text-xs font-medium', preview ? 'text-muted' : 'text-forest-950')}>
        SAWIE ID
      </span>
      <span
        className={cn(
          'mono-id font-semibold tracking-tight text-ink',
          size === 'lg' ? 'text-xl' : 'text-md',
        )}
      >
        {sawieId}
      </span>
      {preview && <span className="text-xs text-muted">Assigned on save</span>}
    </span>
  );
}
