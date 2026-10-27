import { Check } from 'lucide-react';
import { cn } from '@/core/utils/cn';

export interface StepItem {
  key: string;
  label: string;
  description?: string;
}

export interface StepperProps {
  steps: StepItem[];
  /** Index of the current step. Steps before it are complete. */
  current: number;
  orientation?: 'horizontal' | 'vertical';
  onStepClick?: (index: number) => void;
  className?: string;
}

export function Stepper({ steps, current, orientation = 'horizontal', onStepClick, className }: StepperProps) {
  const vertical = orientation === 'vertical';
  return (
    <ol aria-label="Progress" className={cn(vertical ? 'flex flex-col' : 'flex items-start', className)}>
      {steps.map((step, i) => {
        const state = i < current ? 'complete' : i === current ? 'current' : 'upcoming';
        const last = i === steps.length - 1;
        const Marker = onStepClick ? 'button' : 'span';
        return (
          <li key={step.key} className={cn('relative', vertical ? 'flex gap-3 pb-6 last:pb-0' : 'flex flex-1 flex-col items-center text-center')}>
            {!last && (
              <span
                aria-hidden
                className={cn(
                  'absolute',
                  vertical ? 'left-[13px] top-7 h-[calc(100%-28px)] w-px' : 'left-[calc(50%+18px)] top-[13px] h-px w-[calc(100%-36px)]',
                  i < current ? 'bg-forest-600' : 'bg-line',
                )}
              />
            )}
            <Marker
              {...(onStepClick ? { type: 'button' as const, onClick: () => onStepClick(i) } : {})}
              aria-current={state === 'current' ? 'step' : undefined}
              className={cn(
                'relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-sm font-semibold tabular',
                state === 'complete' && 'border-forest-700 bg-forest-700 text-white',
                state === 'current' && 'border-forest-700 bg-surface text-forest-800 ring-4 ring-forest-100',
                state === 'upcoming' && 'border-line bg-surface text-muted',
              )}
            >
              {state === 'complete' ? <Check className="h-3.5 w-3.5" aria-hidden /> : i + 1}
              <span className="sr-only"> {state}</span>
            </Marker>
            <span className={cn(vertical ? 'pt-0.5' : 'mt-2 px-2')}>
              <span className={cn('block text-sm font-medium', state === 'upcoming' ? 'text-muted' : 'text-ink')}>{step.label}</span>
              {step.description && <span className="mt-0.5 block text-xs text-muted">{step.description}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
