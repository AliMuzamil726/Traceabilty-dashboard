import { motion } from 'framer-motion';
import { Check, Circle } from 'lucide-react';
import { formatDate, formatNumber } from '@/core/utils/format';
import { cn } from '@/core/utils/cn';
import type { TimelineStep } from '../api/types';

function when(step: TimelineStep): string | null {
  if (!step.date_from) return null;
  const a = formatDate(step.date_from);
  const b = step.date_to ? formatDate(step.date_to) : a;
  return a === b ? a : `${a} to ${b}`;
}

/** Farm to bale, as a vertical chain of steps. */
export function ChainStepper({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol aria-label="Chain of custody" className="flex flex-col">
      {steps.map((s, i) => (
        <motion.li key={s.key} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04, duration: 0.2 }}
          className="relative flex gap-3 pb-4 last:pb-0">
          {i < steps.length - 1 && <span aria-hidden className={cn('absolute left-[11px] top-6 h-[calc(100%-1.25rem)] w-px', s.done ? 'bg-forest-500' : 'bg-line')} />}
          <span aria-hidden className={cn('z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border',
            s.done ? 'border-forest-700 bg-forest-700 text-white' : 'border-line bg-surface text-muted')}>
            {s.done ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-2.5 w-2.5" />}
          </span>
          <div className="min-w-0 pt-0.5">
            <p className="text-sm font-medium text-ink">
              {s.label}
              {s.count !== null && s.count > 0 && <span className="ml-1.5 text-muted">({formatNumber(s.count)})</span>}
            </p>
            <p className="text-xs text-muted">{when(s) ?? (s.done ? 'Done' : 'Not yet')}</p>
          </div>
        </motion.li>
      ))}
    </ol>
  );
}
