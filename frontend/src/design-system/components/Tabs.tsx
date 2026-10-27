import { motion } from 'framer-motion';
import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import { cn } from '@/core/utils/cn';
import { transition } from '../motion/tokens';

export interface TabItem<T extends string> {
  value: T;
  label: string;
  count?: number;
  disabled?: boolean;
}

export interface TabsProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  items: TabItem<T>[];
  'aria-label': string;
  /** Render the active panel. */
  children?: (value: T) => ReactNode;
}

/** WAI-ARIA tabs with automatic activation (arrow keys, Home, End). */
export function Tabs<T extends string>({ value, onChange, items, children, ...aria }: TabsProps<T>) {
  const base = `tabs${useId().replace(/:/g, '')}`;
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (e: KeyboardEvent, index: number) => {
    const enabled = items.map((t, i) => (t.disabled ? -1 : i)).filter((i) => i >= 0);
    const pos = enabled.indexOf(index);
    let next: number | undefined;
    if (e.key === 'ArrowRight') next = enabled[(pos + 1) % enabled.length];
    else if (e.key === 'ArrowLeft') next = enabled[(pos - 1 + enabled.length) % enabled.length];
    else if (e.key === 'Home') next = enabled[0];
    else if (e.key === 'End') next = enabled[enabled.length - 1];
    if (next === undefined) return;
    e.preventDefault();
    const item = items[next];
    if (item) onChange(item.value);
    refs.current[next]?.focus();
  };

  return (
    <div>
      <div role="tablist" aria-label={aria['aria-label']} className="flex gap-1 border-b border-line">
        {items.map((t, i) => {
          const selected = t.value === value;
          return (
            <button
              key={t.value}
              ref={(el) => {
                refs.current[i] = el;
              }}
              id={`${base}-tab-${t.value}`}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls={`${base}-panel-${t.value}`}
              tabIndex={selected ? 0 : -1}
              disabled={t.disabled}
              onClick={() => onChange(t.value)}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={cn(
                'relative -mb-px flex h-10 items-center gap-2 px-3 text-base font-medium transition-colors duration-fast ease-brand disabled:opacity-50',
                selected ? 'text-forest-800' : 'text-muted hover:text-ink',
              )}
            >
              {t.label}
              {t.count !== undefined && (
                <span className={cn('tabular rounded-pill px-1.5 text-xs', selected ? 'bg-forest-100 text-forest-900' : 'bg-canvas text-muted')}>{t.count}</span>
              )}
              {selected && <motion.span layoutId={`${base}-ind`} className="absolute inset-x-2 bottom-0 h-0.5 rounded-pill bg-forest-700" transition={transition('base')} />}
            </button>
          );
        })}
      </div>
      {children && (
        <div role="tabpanel" id={`${base}-panel-${value}`} aria-labelledby={`${base}-tab-${value}`} tabIndex={0} className="pt-4">
          {children(value)}
        </div>
      )}
    </div>
  );
}
