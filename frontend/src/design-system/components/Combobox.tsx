import { Check, ChevronDown, Loader2, Search } from 'lucide-react';
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { cn } from '@/core/utils/cn';
import { controlClasses } from './controlStyles';
import { useFormField } from './formFieldContext';
import type { SelectOption } from './Select';

export interface ComboboxProps {
  value: string | null;
  onChange: (value: string | null, option: SelectOption | null) => void;
  /** Static options (filtered locally). */
  options?: SelectOption[];
  /** Async search: called with the typed text (debounced). Takes precedence over `options`. */
  loadOptions?: (query: string, signal: AbortSignal) => Promise<SelectOption[]>;
  /** Label for the current value when it is not in the loaded options (async mode). */
  selectedLabel?: string;
  placeholder?: string;
  emptyText?: string;
  invalid?: boolean;
  disabled?: boolean;
  id?: string;
  debounceMs?: number;
  'aria-label'?: string;
  /** Extra content shown at the end of each option row (a status pill, a count). */
  renderMeta?: (option: SelectOption) => ReactNode;
}

/** Searchable single-select following the WAI-ARIA combobox pattern. */
export function Combobox({
  value,
  onChange,
  options = [],
  loadOptions,
  selectedLabel,
  placeholder = 'Search',
  emptyText = 'No matches',
  invalid,
  disabled,
  id,
  debounceMs = 250,
  'aria-label': ariaLabel,
  renderMeta,
}: ComboboxProps) {
  const field = useFormField();
  const inputId = id ?? field?.id;
  const listId = `${useId().replace(/:/g, '')}-list`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [remote, setRemote] = useState<SelectOption[]>([]);
  const [loading, setLoading] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const selected = useMemo(
    () => [...options, ...remote].find((o) => o.value === value) ?? null,
    [options, remote, value],
  );
  const display = open ? query : (selected?.label ?? selectedLabel ?? '');

  useEffect(() => {
    if (!loadOptions || !open) return;
    const controller = new AbortController();
    setLoading(true);
    const timer = window.setTimeout(() => {
      loadOptions(query, controller.signal)
        .then((items) => {
          setRemote(items);
          setActive(0);
        })
        .catch(() => setRemote([]))
        .finally(() => setLoading(false));
    }, debounceMs);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [loadOptions, query, open, debounceMs]);

  const items = useMemo(() => {
    if (loadOptions) return remote;
    const q = query.trim().toLowerCase();
    return q ? options.filter((o) => o.label.toLowerCase().includes(q)) : options;
  }, [loadOptions, remote, options, query]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const choose = (option: SelectOption | undefined) => {
    if (!option || option.disabled) return;
    onChange(option.value, option);
    setOpen(false);
    setQuery('');
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!open) setOpen(true);
      setActive((i) => Math.min(i + 1, Math.max(items.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && open) {
      e.preventDefault();
      choose(items[active]);
    } else if (e.key === 'Escape') {
      setOpen(false);
      setQuery('');
    } else if (e.key === 'Home' && open) {
      setActive(0);
    } else if (e.key === 'End' && open) {
      setActive(Math.max(items.length - 1, 0));
    }
  };

  const isInvalid = invalid ?? field?.invalid ?? false;
  const activeId = open && items[active] ? `${listId}-${active}` : undefined;

  return (
    <div ref={rootRef} className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
      <input
        id={inputId}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        aria-invalid={isInvalid || undefined}
        aria-describedby={field?.describedBy}
        aria-label={ariaLabel}
        autoComplete="off"
        disabled={disabled}
        placeholder={placeholder}
        value={display}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={onKeyDown}
        className={controlClasses(isInvalid, 'h-10 pl-9 pr-9')}
      />
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ChevronDown className="h-4 w-4" />}
      </span>
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-control border border-line bg-surface p-1 shadow-2"
        >
          {items.length === 0 && !loading && <li className="px-3 py-2 text-sm text-muted">{emptyText}</li>}
          {items.map((o, i) => (
            // Keyboard selection is handled on the input via aria-activedescendant.
            // eslint-disable-next-line jsx-a11y/click-events-have-key-events
            <li
              key={o.value}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={o.value === value}
              aria-disabled={o.disabled || undefined}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(o)}
              onMouseEnter={() => setActive(i)}
              className={cn(
                'flex cursor-pointer items-center justify-between rounded-sm px-3 py-2 text-base',
                i === active && 'bg-forest-50',
                o.disabled && 'cursor-not-allowed opacity-50',
              )}
            >
              <span className="min-w-0 truncate">{o.label}</span>
              <span className="ml-2 flex shrink-0 items-center gap-2">
                {renderMeta?.(o)}
                {o.value === value && <Check className="h-4 w-4 text-forest-700" aria-hidden />}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
