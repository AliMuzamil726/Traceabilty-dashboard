import { ChevronDown } from 'lucide-react';
import { forwardRef, type SelectHTMLAttributes } from 'react';
import { cn } from '@/core/utils/cn';
import { controlClasses } from './controlStyles';
import { useFormField } from './formFieldContext';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  /** Options come from the master-list API; never hard-code them in a page. */
  options: SelectOption[];
  placeholder?: string;
  invalid?: boolean;
}

/** Native select (best keyboard, screen-reader and mobile support) with brand styling. */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { options, placeholder, invalid, className, id, required, ...rest },
  ref,
) {
  const field = useFormField();
  const isInvalid = invalid ?? field?.invalid ?? false;
  return (
    <div className="relative w-full min-w-0">
      <select
        ref={ref}
        id={id ?? field?.id}
        required={required ?? field?.required}
        aria-invalid={isInvalid || undefined}
        aria-describedby={rest['aria-describedby'] ?? field?.describedBy}
        className={cn(controlClasses(isInvalid, 'h-10 w-full min-w-0 appearance-none pl-3 pr-9'), className)}
        {...rest}
      >
        {placeholder !== undefined && (
          <option value="" disabled={required ?? field?.required}>
            {placeholder}
          </option>
        )}
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
    </div>
  );
});
