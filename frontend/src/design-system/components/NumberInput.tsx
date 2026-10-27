import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/core/utils/cn';
import { controlClasses } from './controlStyles';
import { useFormField } from './formFieldContext';

export interface NumberInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'value' | 'onChange'> {
  value: number | null | undefined;
  onValueChange: (value: number | null) => void;
  /** Unit shown beside the field. Never rendered inside the input. */
  unit?: string;
  invalid?: boolean;
  decimals?: number;
}

/**
 * Numeric field used across Fieldbook and the rest of the app.
 *
 * Design rules:
 * - Unit is always outside the input (never absolute-positioned inside).
 * - Input keeps a usable minimum width so it never collapses in narrow cards.
 * - Native spinner arrows are hidden; they fight with units and look noisy.
 * - Works in SchemaForm field cards, PairedNumberInput, and wide layouts.
 */
export const NumberInput = forwardRef<HTMLInputElement, NumberInputProps>(function NumberInput(
  {
    value,
    onValueChange,
    unit,
    decimals,
    step,
    className,
    invalid,
    id,
    required,
    disabled,
    readOnly,
    min,
    max,
    ...rest
  },
  ref,
) {
  const field = useFormField();
  const isInvalid = invalid ?? field?.invalid ?? false;

  return (
    <div className={cn('flex w-full min-w-0 items-center gap-2', className)}>
      <input
        ref={ref}
        id={id ?? field?.id}
        type="number"
        inputMode={decimals === 0 ? 'numeric' : 'decimal'}
        step={step ?? (decimals === undefined ? 'any' : decimals === 0 ? 1 : 1 / 10 ** decimals)}
        min={min}
        max={max}
        value={value ?? ''}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === '') return onValueChange(null);
          const parsed = Number(raw);
          onValueChange(Number.isFinite(parsed) ? parsed : null);
        }}
        required={required ?? field?.required}
        disabled={disabled}
        readOnly={readOnly}
        aria-invalid={isInvalid || undefined}
        aria-describedby={rest['aria-describedby'] ?? field?.describedBy}
        className={cn(
          controlClasses(isInvalid, 'h-10 min-w-[5.5rem] flex-1 px-3'),
          // Hide native number spinners (Chrome, Safari, Edge, Firefox)
          '[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none',
          'tabular-nums text-right',
        )}
        {...rest}
      />
      {unit ? (
        <span
          className="max-w-[9rem] shrink-0 select-none text-sm leading-snug text-muted sm:max-w-none"
          aria-hidden
        >
          {unit}
        </span>
      ) : null}
    </div>
  );
});
