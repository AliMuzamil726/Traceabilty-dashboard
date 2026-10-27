import {
  Boxes,
  ClipboardList,
  MapPin,
  QrCode,
  Scissors,
  Truck,
  Users,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Skeleton } from '@/design-system/components/Skeleton';
import type { Pipeline, StageKey } from '../api/types';
import { StageCard } from './StageCard';

const ICONS: Record<StageKey, LucideIcon> = {
  farmers: Users,
  fields: MapPin,
  fieldbooks: ClipboardList,
  harvest: Scissors,
  deliveries: Truck,
  bales: Boxes,
  scans: QrCode,
};

export interface PipelineTrackerProps {
  data: Pipeline | undefined;
  loading: boolean;
}

/**
 * The whole chain at a glance: seven connected stages from registered farmer to
 * scanned code. A horizontal sequence on a wide screen, a vertical stepper on a
 * phone, where seven columns would be unreadable.
 */
export function PipelineTracker({ data, loading }: PipelineTrackerProps) {

  if (loading && !data) {
    return (
      <div className="grid gap-px overflow-hidden rounded-card border border-line bg-line sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {Array.from({ length: 7 }, (_, i) => (
          <Skeleton key={i} className="h-[152px] w-full rounded-none" shape="block" />
        ))}
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="relative">
      {/* One bordered strip, cells divided by hairlines: reads as a sequence, not seven cards. */}
      <ol className="relative grid gap-px overflow-hidden rounded-card border border-line bg-line shadow-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {data.stages.map((stage, index) => (
          <StageCard
            key={stage.key}
            stage={stage}
            icon={ICONS[stage.key]}
            index={index}
            showConversion={index > 0}
          />
        ))}
        {/* Fills the empty cell left by seven stages in two or four columns. */}
        <li aria-hidden className="hidden bg-surface sm:block xl:hidden" />
      </ol>
    </div>
  );
}

