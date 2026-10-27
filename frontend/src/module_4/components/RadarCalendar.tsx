import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/core/utils/cn';
import { formatNumber } from '@/core/utils/format';
import { IconButton, Skeleton } from '@/design-system/components';
import type { CalendarData } from '../api/types';
import { monthGrid, shiftMonth } from '../lib/calendar';

export interface RadarCalendarProps {
  month: string; // YYYY-MM
  data: CalendarData | undefined;
  loading: boolean;
  selectedDay: string | null;
  onMonthChange: (month: string) => void;
  onPickDay: (day: string) => void;
}

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function kg(value: number): string {
  return value >= 1000 ? `${formatNumber(value / 1000, 1)} t` : `${formatNumber(value)} kg`;
}

/** Expected-ready dates for a month. Clicking a day filters the table to that day. */
export function RadarCalendar({ month, data, loading, selectedDay, onMonthChange, onPickDay }: RadarCalendarProps) {
  const byDay = new Map((data?.days ?? []).map((d) => [d.date, d]));
  const today = new Date().toISOString().slice(0, 10);
  const title = new Date(`${month}-01T00:00:00Z`).toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' });

  return (
    <section aria-labelledby="calendar-title" className="rounded-card border border-line bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="calendar-title" className="text-md font-semibold text-ink">
          Expected ready dates, {title}
        </h2>
        <div className="flex gap-1">
          <IconButton label="Previous month" icon={<ChevronLeft className="h-4 w-4" />} onClick={() => onMonthChange(shiftMonth(month, -1))} />
          <IconButton label="Next month" icon={<ChevronRight className="h-4 w-4" />} onClick={() => onMonthChange(shiftMonth(month, 1))} />
        </div>
      </div>
      {loading && !data ? (
        <Skeleton className="h-72 w-full" shape="block" />
      ) : (
        <div role="grid" aria-label={`Expected ready dates in ${title}`} className="grid grid-cols-7 gap-1">
          {WEEKDAYS.map((d) => (
            <div key={d} role="columnheader" className="pb-1 text-center text-xs font-medium text-muted">
              {d}
            </div>
          ))}
          {monthGrid(month).map((day, i) => {
            if (!day) return <div key={`pad-${i}`} aria-hidden />;
            const hit = byDay.get(day);
            const selected = selectedDay === day;
            return (
              <button
                key={day}
                type="button"
                role="gridcell"
                aria-selected={selected}
                disabled={!hit}
                aria-label={hit ? `${day}: ${hit.fields} fields, about ${kg(hit.estimated_kg)}` : `${day}: none`}
                onClick={() => onPickDay(day)}
                className={cn(
                  'flex min-h-[72px] flex-col items-start rounded-control border p-2 text-left',
                  hit ? 'border-forest-100 bg-forest-50 hover:border-forest-600' : 'border-line bg-surface text-muted',
                  selected && 'border-forest-700 ring-2 ring-forest-700',
                  day === today && 'border-wheat-500',
                )}
              >
                <span className="tabular text-xs">{Number(day.slice(8))}</span>
                {hit && (
                  <>
                    <span className="tabular mt-auto text-sm font-semibold text-forest-900">
                      {hit.fields} {hit.fields === 1 ? 'field' : 'fields'}
                    </span>
                    <span className="tabular text-xs text-muted">{kg(hit.estimated_kg)}</span>
                  </>
                )}
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
