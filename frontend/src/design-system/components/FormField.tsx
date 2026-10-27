import { useId, type ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';
import { cn } from '@/core/utils/cn';
import { FormFieldContext } from './formFieldContext';

export interface FormFieldProps {
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  id?: string;
  className?: string;
  /** Visually hide the label (it stays available to screen readers). */
  hideLabel?: boolean;
  children: ReactNode;
}

export function FormField({
  label,
  hint,
  error,
  required = false,
  id,
  className,
  hideLabel,
  children,
}: FormFieldProps) {
  const autoId = useId();
  const fieldId = id ?? `f${autoId.replace(/:/g, '')}`;
  const hintId = hint ? `${fieldId}-hint` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined;

  return (
    <FormFieldContext.Provider value={{ id: fieldId, describedBy, invalid: Boolean(error), required }}>
      <div className={cn('flex min-w-0 flex-col gap-1.5', className)}>
        <label
          htmlFor={fieldId}
          className={cn('text-sm font-medium leading-snug text-ink', hideLabel && 'sr-only')}
        >
          {label}
          {required && (
            <span className="ml-0.5 text-danger" aria-hidden>
              *
            </span>
          )}
          {required && <span className="sr-only"> (required)</span>}
        </label>
        {children}
        {error ? (
          <p id={errorId} className="flex items-center gap-1 text-sm text-danger" role="alert">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden />
            {error}
          </p>
        ) : hint ? (
          <p id={hintId} className="text-sm text-muted">
            {hint}
          </p>
        ) : null}
      </div>
    </FormFieldContext.Provider>
  );
}
