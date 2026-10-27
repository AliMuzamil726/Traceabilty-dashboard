import { motion } from 'framer-motion';
import { ArrowRight, Check } from 'lucide-react';
import { Link as RouterLink } from 'react-router-dom';
import { cn } from '@/core/utils/cn';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { buttonClasses } from '@/design-system/components/buttonStyles';
import { listItemVariants } from '@/design-system/motion';
import type { Onboarding } from '../api/types';
import { toHref } from '../lib/links';

export interface GetStartedProps {
  data: Onboarding;
}

/**
 * The first thing an officer sees on an empty database: the three steps that make the
 * rest of the product work, each a link to where it is done. The steps tick off as the
 * work happens, so the checklist stays useful while the first farmers are registered.
 */
export function GetStarted({ data }: GetStartedProps) {
  const next = data.steps.find((step) => !step.done);
  return (
    <Card as="section" aria-labelledby="get-started-heading" padding="lg">
      <SectionHeader
        id="get-started-heading"
        title="Get started"
        description={
          data.role === 'admin'
            ? 'Nothing has been recorded yet. The officers start here, and the figures follow.'
            : 'Three steps, and the whole chain from farmer to bale starts filling in.'
        }
      />
      <ol className="mt-5 flex flex-col gap-3">
        {data.steps.map((step, index) => (
          <motion.li
            key={step.key}
            custom={index}
            variants={listItemVariants}
            initial="initial"
            animate="animate"
            className={cn(
              'flex flex-col gap-3 rounded-control border p-4 sm:flex-row sm:items-center sm:justify-between',
              step.done ? 'border-forest-100 bg-forest-50' : 'border-line bg-surface',
            )}
          >
            <div className="flex min-w-0 items-start gap-3">
              <span
                className={cn(
                  'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-sm font-medium',
                  step.done
                    ? 'border-forest-600 bg-forest-600 text-white'
                    : 'border-line bg-canvas text-muted',
                )}
                aria-hidden
              >
                {step.done ? <Check className="h-4 w-4" /> : index + 1}
              </span>
              <div className="min-w-0">
                <p className="font-medium text-ink">
                  {step.title}
                  {step.done && <span className="sr-only"> (done)</span>}
                </p>
                <p className="mt-0.5 text-sm text-muted">{step.description}</p>
              </div>
            </div>
            <RouterLink
              to={toHref(step.link)}
              className={cn(
                buttonClasses(step.key === next?.key ? 'primary' : 'secondary', 'sm'),
                'shrink-0',
              )}
            >
              <span>{step.done ? 'Open' : 'Start'}</span>
              <ArrowRight className="h-4 w-4" aria-hidden />
            </RouterLink>
          </motion.li>
        ))}
      </ol>
    </Card>
  );
}
