import { useRef, type KeyboardEvent, type ReactNode } from 'react';
import { cn } from '@/core/utils/cn';

export interface ChoiceCardOption<T extends string> {
  value: T;
  title: string;
  description?: string;
  icon?: ReactNode;
  disabled?: boolean;
}

export interface ChoiceCardsProps<T extends string> {
  value: T | null;
  onChange: (value: T) => void;
  options: ChoiceCardOption<T>[];
  'aria-label': string;
  columns?: 2 | 3 | 4;
  invalid?: boolean;
}

/** Large radio cards for choices that benefit from a description (e.g. land tenure). */
export function ChoiceCards<T extends string>({ value, onChange, options, columns = 3, invalid, ...aria }: ChoiceCardsProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const focusIndex = Math.max(0, options.findIndex((o) => o.value === value));

  const move = (e: KeyboardEvent, index: number) => {
    if (!['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp'].includes(e.key)) return;
    e.preventDefault();
    const dir = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : -1;
    for (let step = 1; step <= options.length; step++) {
      const next = (index + dir * step + options.length) % options.length;
      const option = options[next];
      if (option && !option.disabled) {
        onChange(option.value);
        refs.current[next]?.focus();
        return;
      }
    }
  };

  return (
    <div
      role="radiogroup"
      aria-label={aria['aria-label']}
      aria-invalid={invalid || undefined}
      className={cn('grid gap-3', columns === 2 && 'sm:grid-cols-2', columns === 3 && 'sm:grid-cols-3', columns === 4 && 'sm:grid-cols-2 lg:grid-cols-4')}
    >
      {options.map((o, i) => {
        const checked = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={i === focusIndex ? 0 : -1}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => move(e, i)}
            className={cn(
              'flex items-start gap-3 rounded-card border bg-surface p-4 text-left',
              'transition-[border-color,background-color,box-shadow] duration-fast ease-brand disabled:opacity-50',
              checked ? 'border-forest-700 bg-forest-50 shadow-1' : invalid ? 'border-danger' : 'border-line hover:border-forest-500/40',
            )}
          >
            <span
              aria-hidden
              className={cn(
                'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border',
                checked ? 'border-forest-700' : 'border-muted/60',
              )}
            >
              {checked && <span className="h-2 w-2 rounded-full bg-forest-700" />}
            </span>
            <span className="flex flex-col gap-1">
              <span className="flex items-center gap-2 font-medium text-ink">
                {o.icon && <span className="text-forest-700 [&>svg]:h-4 [&>svg]:w-4">{o.icon}</span>}
                {o.title}
              </span>
              {o.description && <span className="text-sm text-muted">{o.description}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
