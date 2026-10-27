import { Check, Minus } from 'lucide-react';
import { cn } from '@/core/utils/cn';
import { ProgressBar } from '@/design-system/components';
import type { StepDef, StepState } from '../api/types';
import { stepDone } from '../lib/schemaLogic';

export interface FormStepperProps {
  steps: StepDef[];
  states: StepState[];
  current: string;
  onSelect: (key: string) => void;
  /** Steps with blocking errors, marked so the officer can find them. */
  errorSteps?: Set<string>;
}

function statusText(state: StepState | undefined): string {
  if (state?.status === 'complete') return 'complete';
  if (state?.status === 'not_applicable') return 'nothing to record';
  if (state?.status === 'in_progress') return 'in progress';
  return 'not started';
}

/**
 * Step navigation. Completion is per step, not positional: an officer can record a
 * picking before the weeding, so each step shows its own state.
 */
export function FormStepper({ steps, states, current, onSelect, errorSteps = new Set() }: FormStepperProps) {
  const byKey = new Map(states.map((s) => [s.key, s]));
  const done = steps.filter((s) => stepDone(byKey.get(s.key))).length;

  return (
    <nav aria-label="Fieldbook steps">
      {/* Mobile and tablet: a compact horizontal progress strip. */}
      <div className="lg:hidden">
        <ProgressBar value={done} max={steps.length} label={`${done} of ${steps.length} steps done`} showValue />
        <ol className="mt-3 flex gap-1.5 overflow-x-auto pb-1">
          {steps.map((step, i) => {
            const state = byKey.get(step.key);
            return (
              <li key={step.key}>
                <button
                  type="button"
                  onClick={() => onSelect(step.key)}
                  aria-current={step.key === current ? 'step' : undefined}
                  aria-label={`${step.title}, ${statusText(state)}`}
                  className={cn(
                    'flex h-8 min-w-8 items-center justify-center rounded-full border px-2 text-xs font-semibold tabular transition-colors',
                    step.key === current && 'ring-2 ring-forest-500 bg-forest-50 text-forest-900 border-forest-600',
                    stepDone(state) ? 'border-forest-700 bg-forest-700 text-white' : 'border-line bg-surface text-muted',
                    errorSteps.has(step.key) && 'border-danger text-danger',
                  )}
                >
                  {i + 1}
                </button>
              </li>
            );
          })}
        </ol>
      </div>

      {/* Desktop: the full vertical list with progress header. */}
      <div className="hidden flex-col gap-3 lg:flex">
        <div className="border-b border-line pb-3">
          <ProgressBar value={done} max={steps.length} label={`${done} of ${steps.length} steps done`} showValue />
        </div>
        <ol className="flex flex-col gap-1">
          {steps.map((step, i) => {
            const state = byKey.get(step.key);
            const isCurrent = step.key === current;
            const na = state?.status === 'not_applicable';
            return (
              <li key={step.key}>
                <button
                  type="button"
                  onClick={() => onSelect(step.key)}
                  aria-current={isCurrent ? 'step' : undefined}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-control px-2.5 py-2 text-left text-sm transition-colors',
                    isCurrent
                      ? 'bg-forest-50 font-semibold text-forest-900 ring-1 ring-forest-500/30'
                      : 'text-ink hover:bg-canvas',
                  )}
                >
                  <span
                    className={cn(
                      'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular',
                      stepDone(state)
                        ? 'border-forest-700 bg-forest-700 text-white'
                        : isCurrent
                          ? 'border-forest-600 bg-surface text-forest-800'
                          : 'border-line bg-surface text-muted',
                      errorSteps.has(step.key) && 'border-danger bg-surface text-danger',
                    )}
                  >
                    {na ? <Minus className="h-3 w-3" aria-hidden /> : stepDone(state) ? <Check className="h-3 w-3" aria-hidden /> : i + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className={cn('block truncate', isCurrent && 'font-semibold')}>{step.title}</span>
                    {(state?.entry_count ?? 0) > 0 && step.repeatable && (
                      <span className="block text-xs text-muted">
                        {state?.entry_count} {state?.entry_count === 1 ? 'entry' : 'entries'}
                      </span>
                    )}
                  </span>
                  <span className="sr-only">{statusText(state)}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>
    </nav>
  );
}
