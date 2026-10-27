import { cn } from '@/core/utils/cn';
import { Badge, Card } from '@/design-system/components';
import type { CropClock, CropStatus } from '../api/types';

export interface CropClockBarProps {
  clock: CropClock;
  status: CropStatus;
}

const TONE: Record<string, 'neutral' | 'info' | 'warning' | 'success' | 'accent'> = {
  no_sowing_data: 'neutral',
  growing: 'info',
  approaching: 'warning',
  ready: 'accent',
  harvested: 'success',
};

/** Days after sowing against the crop's harvest milestones. */
export function CropClockBar({ clock, status }: CropClockBarProps) {
  const span = clock.window_end_day + 20;
  const pct = (d: number) => `${Math.min(100, (d / span) * 100)}%`;
  const das = status.days_after_sowing;

  return (
    <Card padding="md" aria-label="Crop clock">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">Crop clock</h3>
        <Badge tone={TONE[status.status] ?? 'neutral'} dot size="sm">
          {status.label}
          {status.overdue ? ', overdue' : ''}
        </Badge>
      </div>
      <div className="relative mt-4 h-2 rounded-full bg-canvas" role="img" aria-label={das === null ? 'No sowing date yet' : `Day ${das} after sowing`}>
        <span className="absolute inset-y-0 rounded-full bg-wheat-100" style={{ left: pct(clock.ready_day), width: `calc(${pct(clock.window_end_day)} - ${pct(clock.ready_day)})` }} />
        {das !== null && (
          <span className={cn('absolute inset-y-0 left-0 rounded-full', status.overdue ? 'bg-wheat-600' : 'bg-forest-600')} style={{ width: pct(Math.max(0, das)) }} />
        )}
        {[clock.approach_day, clock.ready_day, clock.window_end_day].map((d) => (
          <span key={d} className="absolute -top-1 h-4 w-px bg-ink/30" style={{ left: pct(d) }} />
        ))}
      </div>
      <div className="mt-2 flex justify-between text-xs text-muted tabular">
        <span>Sowing</span>
        <span>Day {clock.ready_day}</span>
        <span>Day {clock.window_end_day}</span>
      </div>
      <p className="mt-3 text-sm text-ink">
        {das === null ? status.next_milestone : <><span className="font-semibold tabular">Day {das}</span>. {status.next_milestone}</>}
      </p>
    </Card>
  );
}
