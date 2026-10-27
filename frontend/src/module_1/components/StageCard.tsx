import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Link as RouterLink } from 'react-router-dom';
import { formatNumber } from '@/core/utils/format';
import { listItemVariants, transition } from '@/design-system/motion';
import type { Stage } from '../api/types';
import { percent } from '../lib/format';
import { toHref } from '../lib/links';
import { useCountUp } from '../hooks/useCountUp';

export interface StageCardProps {
  stage: Stage;
  icon: LucideIcon;
  index: number;
  /** Shown between stages: the share that reached this one from the one before. */
  showConversion: boolean;
}

/**
 * One stage of the pipeline: a count, how far it is from the first stage, and the
 * share that came through from the stage before. The whole card is the link into the
 * module that owns these records, with the filters that produced the number.
 */
export function StageCard({ stage, icon: Icon, index, showConversion }: StageCardProps) {
  const value = useCountUp(stage.count);
  return (
    <motion.li
      custom={index}
      variants={listItemVariants}
      initial="initial"
      animate="animate"
      className="relative min-w-0"
    >
      <RouterLink
        to={toHref(stage.link)}
        className="group flex h-full min-w-0 flex-col gap-3 bg-surface p-4 transition-colors duration-base ease-brand hover:bg-forest-50"
      >
        <span className="flex min-h-[36px] min-w-0 items-start justify-between gap-2 xl:min-h-[54px]">
          <span className="flex min-w-0 items-start gap-2 text-sm font-medium leading-snug text-muted">
            <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span className="min-w-0 break-words">{stage.title}</span>
          </span>
          <ArrowRight
            className="mt-0.5 h-4 w-4 shrink-0 text-transparent transition-colors duration-base group-hover:text-forest-600 group-focus-visible:text-forest-600"
            aria-hidden
          />
        </span>

        <span className="tabular-nums text-2xl font-semibold tracking-[-0.02em] text-ink">
          {formatNumber(value)}
        </span>

        <span className="flex min-w-0 flex-col gap-1.5">
          <span
            className="h-1 overflow-hidden rounded-pill bg-line/70"
            role="img"
            aria-label={`${percent(stage.progress_pct)} of the first stage`}
          >
            <motion.span
              className="block h-full rounded-pill bg-forest-600"
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(100, stage.progress_pct)}%` }}
              transition={transition('slow')}
            />
          </span>
          {showConversion && stage.conversion_pct !== null && stage.conversion_pct <= 100 && (
            <span className="tabular-nums text-xs text-muted">
              {percent(stage.conversion_pct, 1)} of the stage before
            </span>
          )}
          {stage.detail && (
            <span className="break-words text-xs leading-snug text-muted">{stage.detail}</span>
          )}
        </span>
      </RouterLink>
    </motion.li>
  );
}
