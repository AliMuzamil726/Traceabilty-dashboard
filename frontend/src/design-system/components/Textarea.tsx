import { forwardRef, type TextareaHTMLAttributes } from 'react';
import { cn } from '@/core/utils/cn';
import { controlClasses } from './controlStyles';
import { useFormField } from './formFieldContext';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { invalid, className, id, rows = 4, required, ...rest },
  ref,
) {
  const field = useFormField();
  const isInvalid = invalid ?? field?.invalid ?? false;
  return (
    <textarea
      ref={ref}
      id={id ?? field?.id}
      rows={rows}
      required={required ?? field?.required}
      aria-invalid={isInvalid || undefined}
      aria-describedby={rest['aria-describedby'] ?? field?.describedBy}
      className={cn(controlClasses(isInvalid, 'px-3 py-2.5 leading-relaxed'), 'resize-y', className)}
      {...rest}
    />
  );
});
