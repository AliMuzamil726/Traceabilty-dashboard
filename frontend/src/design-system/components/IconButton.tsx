import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/core/utils/cn';

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  /** Accessible name. Read by screen readers; never drawn on screen. */
  label: string;
  icon: ReactNode;
  size?: 'sm' | 'md';
  variant?: 'ghost' | 'secondary' | 'onDark';
}

const VARIANTS = {
  ghost: 'text-muted hover:bg-forest-50 hover:text-forest-800',
  secondary: 'border border-line bg-surface text-ink hover:bg-forest-50',
  onDark: 'text-forest-100 hover:bg-white/10 hover:text-white',
} as const;

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, size = 'md', variant = 'ghost', className, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      className={cn(
        'inline-flex items-center justify-center rounded-control transition-colors duration-fast ease-brand',
        'motion-safe:active:scale-[.98] disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'h-8 w-8' : 'h-10 w-10',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {icon}
    </button>
  );
});
