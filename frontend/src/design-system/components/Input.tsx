import { Eye, EyeOff } from 'lucide-react';
import { forwardRef, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/core/utils/cn';
import { controlClasses } from './controlStyles';
import { useFormField } from './formFieldContext';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
  leadingIcon?: ReactNode;
  /** Short suffix only (e.g. icons or 2–4 chars). Long units must use NumberInput. */
  suffix?: ReactNode;
  mono?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid, leadingIcon, suffix, mono, className, id, required, type, ...rest },
  ref,
) {
  const field = useFormField();
  const isInvalid = invalid ?? field?.invalid ?? false;
  const isPassword = type === 'password';
  const [showPassword, setShowPassword] = useState(false);

  const resolvedType = isPassword ? (showPassword ? 'text' : 'password') : type;

  // Long string suffixes (units) break absolute positioning — keep them outside.
  const suffixText = typeof suffix === 'string' ? suffix : '';
  const longSuffix = Boolean(suffixText && suffixText.length > 6);

  return (
    <div className={cn('relative flex w-full min-w-0 items-center', longSuffix && 'gap-2')}>
      {leadingIcon && (
        <span className="pointer-events-none absolute left-3 text-muted [&>svg]:h-4 [&>svg]:w-4" aria-hidden>
          {leadingIcon}
        </span>
      )}
      <input
        ref={ref}
        id={id ?? field?.id}
        type={resolvedType}
        required={required ?? field?.required}
        aria-invalid={isInvalid || undefined}
        aria-describedby={rest['aria-describedby'] ?? field?.describedBy}
        className={cn(
          controlClasses(isInvalid, 'h-10 w-full min-w-0 px-3'),
          leadingIcon ? 'pl-9' : undefined,
          !longSuffix && suffix ? 'pr-12' : isPassword ? 'pr-10' : undefined,
          mono && 'mono-id',
          className,
        )}
        {...rest}
      />
      {isPassword ? (
        <button
          type="button"
          onClick={() => setShowPassword((prev) => !prev)}
          aria-label={showPassword ? 'Hide password' : 'Show password'}
          title={showPassword ? 'Hide password' : 'Show password'}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-control p-1.5 text-muted transition-colors hover:bg-canvas hover:text-ink"
        >
          {showPassword ? (
            <EyeOff className="h-4 w-4" aria-hidden />
          ) : (
            <Eye className="h-4 w-4" aria-hidden />
          )}
        </button>
      ) : longSuffix ? (
        <span className="shrink-0 select-none text-sm text-muted whitespace-nowrap" aria-hidden>
          {suffix}
        </span>
      ) : (
        suffix && (
          <span className="pointer-events-none absolute right-3 text-sm text-muted" aria-hidden>
            {suffix}
          </span>
        )
      )}
    </div>
  );
});
