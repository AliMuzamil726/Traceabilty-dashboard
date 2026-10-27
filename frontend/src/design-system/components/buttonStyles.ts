import { cn } from '@/core/utils/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-forest-700 text-white hover:bg-forest-800 active:bg-forest-900 shadow-1',
  secondary: 'bg-surface text-ink border border-line hover:border-forest-500/40 hover:bg-forest-50',
  ghost: 'bg-transparent text-forest-800 hover:bg-forest-50',
  danger: 'bg-danger text-white hover:brightness-95 shadow-1',
};

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm gap-1.5',
  md: 'h-10 px-4 text-base gap-2',
  lg: 'h-12 px-5 text-md gap-2',
};

/** Button look as a class string (also used to style links as buttons). */
export const buttonClasses = (variant: ButtonVariant = 'primary', size: ButtonSize = 'md') =>
  cn(
    'inline-flex select-none items-center justify-center rounded-control font-medium',
    'transition-[background-color,border-color,transform,filter] duration-fast ease-brand',
    'motion-safe:active:scale-[.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100',
    VARIANTS[variant],
    SIZES[size],
  );

