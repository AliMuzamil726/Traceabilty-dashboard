import { CircleCheck, CircleX } from 'lucide-react';
import { cn } from '@/core/utils/cn';
import type { Check } from '../api/types';

/** The four honesty checks. A failed check is shown plainly, never hidden. */
export function VerificationPanel({ checks, title = 'Verification' }: { checks: Check[]; title?: string }) {
  const passed = checks.filter((c) => c.passed).length;
  return (
    <section aria-label={title} className="rounded-card border border-line bg-surface p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        <span className="text-xs text-muted">{passed} of {checks.length} checks passed</span>
      </div>
      <ul className="mt-3 flex flex-col gap-2.5">
        {checks.map((c) => (
          <li key={c.key} data-check={c.key} data-passed={c.passed} className="flex items-start gap-2.5">
            {c.passed
              ? <CircleCheck aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-forest-600" />
              : <CircleX aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-danger" />}
            <div className="min-w-0">
              <p className={cn('text-sm font-medium', c.passed ? 'text-ink' : 'text-danger')}>
                {c.label}<span className="sr-only">{c.passed ? ': passed' : ': not passed'}</span>
              </p>
              <p className="text-xs text-muted">{c.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
