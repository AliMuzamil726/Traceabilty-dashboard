import { cn } from '@/core/utils/cn';

/** Shared look for text-like controls (Input, Select, Textarea, Combobox, DatePicker). */
export function controlClasses(invalid: boolean, extra?: string): string {
  return cn(
    'w-full rounded-control border bg-surface text-base text-ink placeholder:text-muted/80',
    'transition-[border-color,box-shadow] duration-fast ease-brand',
    'focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-500',
    'disabled:cursor-not-allowed disabled:bg-canvas disabled:text-muted',
    invalid ? 'border-danger' : 'border-line hover:border-forest-500/40',
    extra,
  );
}
