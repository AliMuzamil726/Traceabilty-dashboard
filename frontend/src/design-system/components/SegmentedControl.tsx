import { motion } from 'framer-motion';
import { useId, useRef, type KeyboardEvent } from 'react';
import { cn } from '@/core/utils/cn';
import { transition } from '../motion/tokens';

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  disabled?: boolean;
}

export interface SegmentedControlProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: SegmentOption<T>[];
  'aria-label': string;
  size?: 'sm' | 'md';
}

/** Radio group styled as a segmented switch. Arrow keys move the selection. */
export function SegmentedControl<T extends string>({ value, onChange, options, size = 'md', ...aria }: SegmentedControlProps<T>) {
  const layoutId = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

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
    <div role="radiogroup" aria-label={aria['aria-label']} className="inline-flex rounded-control border border-line bg-canvas p-0.5">
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
            tabIndex={checked ? 0 : -1}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => move(e, i)}
            className={cn(
              'relative rounded-[8px] font-medium transition-colors duration-fast ease-brand disabled:opacity-50',
              size === 'sm' ? 'h-7 px-3 text-sm' : 'h-9 px-4 text-base',
              checked ? 'text-forest-900' : 'text-muted hover:text-ink',
            )}
          >
            {checked && (
              <motion.span
                layoutId={layoutId}
                className="absolute inset-0 rounded-[8px] border border-line bg-surface shadow-1"
                transition={transition('base')}
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
