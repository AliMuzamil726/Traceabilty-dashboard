import { motion } from 'framer-motion';
import { useId } from 'react';
import { cn } from '@/core/utils/cn';
import { transition } from '@/design-system/motion';

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Visible label. Use `hideLabel` when the context already names the setting. */
  label: string;
  hideLabel?: boolean;
  description?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}

/**
 * On/off control for a single setting.
 *
 * A real checkbox underneath, so it is announced and operated the way a screen reader
 * and a keyboard expect; the track and knob are drawn on top. Use it where a choice is
 * genuinely two-state and takes effect as a whole, not for filters (SegmentedControl)
 * or for picking one of several values (Select).
 */
export function Switch({
  checked,
  onChange,
  label,
  hideLabel,
  description,
  disabled,
  id,
  className,
}: SwitchProps) {
  const generated = `sw${useId().replace(/:/g, '')}`;
  const inputId = id ?? generated;
  const descId = description ? `${inputId}-desc` : undefined;

  return (
    <div className={cn('flex items-start gap-3', className)}>
      <span className="relative inline-flex shrink-0 items-center">
        <input
          id={inputId}
          type="checkbox"
          role="switch"
          checked={checked}
          disabled={disabled}
          aria-describedby={descId}
          onChange={(event) => onChange(event.target.checked)}
          className="peer absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
        />
        <span
          aria-hidden
          className={cn(
            'flex h-6 w-11 items-center rounded-pill border p-0.5 transition-colors duration-base ease-brand',
            'peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-forest-500',
            checked ? 'border-forest-700 bg-forest-700' : 'border-line bg-canvas',
            disabled && 'opacity-50',
          )}
        >
          <motion.span
            layout
            transition={transition('fast')}
            className={cn(
              'h-5 w-5 rounded-full bg-surface shadow-1',
              checked ? 'ml-auto' : 'mr-auto',
            )}
          />
        </span>
      </span>
      <span className={cn('min-w-0', hideLabel && 'sr-only')}>
        <label htmlFor={inputId} className="block text-base font-medium text-ink">
          {label}
        </label>
        {description && (
          <span id={descId} className="mt-0.5 block text-sm text-muted">
            {description}
          </span>
        )}
      </span>
    </div>
  );
}
