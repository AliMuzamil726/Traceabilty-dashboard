import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { PIPELINE, statusLabel } from '@/app/moduleRegistry';
import { cn } from '@/core/utils/cn';
import { StatusPill } from '@/design-system/components/Badge';
import { listItemVariants } from '@/design-system/motion';

export interface PipelineTrackerProps {
  /** Highlight one stage (module number), e.g. on a module placeholder. */
  highlight?: number;
  compact?: boolean;
  className?: string;
}

/**
 * The farm-to-bale chain as connected stages. Stages are a real sequence, so they are
 * numbered; the connecting line is the "thread" from farmer to bale.
 */
export function PipelineTracker({ highlight, compact = false, className }: PipelineTrackerProps) {
  return (
    <ol aria-label="Traceability pipeline" className={cn('relative grid gap-3 md:grid-cols-3 xl:grid-cols-6 xl:gap-0', className)}>
      <span aria-hidden className="absolute left-[13%] right-[13%] top-[34px] hidden h-px bg-gradient-to-r from-forest-600 via-wheat-500 to-wheat-300 xl:block" />
      {PIPELINE.map((stage, i) => {
        const Icon = stage.icon;
        const label = statusLabel(stage);
        const active = highlight === stage.number;
        const dimmed = highlight !== undefined && !active;
        return (
          <motion.li key={stage.number} custom={i} variants={listItemVariants} initial="initial" animate="animate" className="relative xl:px-2">
            <Link
              to={stage.path}
              className={cn(
                'flex h-full items-start gap-3 rounded-card border bg-surface p-4 transition-[border-color,box-shadow] duration-base ease-brand xl:flex-col xl:items-center xl:text-center',
                active ? 'border-forest-700 shadow-2' : 'border-line hover:border-forest-500/40 hover:shadow-1',
              )}
              aria-current={active ? 'page' : undefined}
            >
              <span
                className={cn(
                  'relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border',
                  active ? 'border-forest-700 bg-forest-700 text-white' : 'border-line bg-forest-50 text-forest-700',
                )}
                aria-hidden
              >
                <Icon className="h-4 w-4" />
              </span>
              <span className="flex min-w-0 flex-1 flex-col gap-1.5 self-stretch xl:items-center">
                <span className="mono-id text-xs text-muted">Stage {stage.pipelineStage}</span>
                <span className={cn('font-semibold', dimmed ? 'text-muted' : 'text-ink')}>{stage.name}</span>
                {!compact && <span className="text-sm text-muted">{stage.purpose}</span>}
                {label && (
                  <span className="mt-1 xl:mt-auto xl:pt-2">
                    <StatusPill size="sm" tone={label === 'In build' ? 'accent' : 'neutral'}>
                      {label}
                    </StatusPill>
                  </span>
                )}
              </span>
            </Link>
          </motion.li>
        );
      })}
    </ol>
  );
}
