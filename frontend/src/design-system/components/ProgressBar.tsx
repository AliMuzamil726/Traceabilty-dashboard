import { motion } from 'framer-motion';
import { cn } from '@/core/utils/cn';
import { transition } from '../motion/tokens';

export interface ProgressBarProps {
  /** 0 to `max`. */
  value: number;
  max?: number;
  label: string;
  showValue?: boolean;
  tone?: 'forest' | 'wheat';
  className?: string;
}

export function ProgressBar({ value, max = 100, label, showValue, tone = 'forest', className }: ProgressBarProps) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {showValue && (
        <div className="flex justify-between text-sm">
          <span className="text-muted">{label}</span>
          <span className="tabular font-medium text-ink">{Math.round(pct)}%</span>
        </div>
      )}
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        className="h-2 overflow-hidden rounded-pill bg-line/70"
      >
        <motion.div
          className={cn('h-full rounded-pill', tone === 'forest' ? 'bg-forest-600' : 'bg-wheat-500')}
          initial={false}
          animate={{ width: `${pct}%` }}
          transition={transition('slow')}
        />
      </div>
    </div>
  );
}
