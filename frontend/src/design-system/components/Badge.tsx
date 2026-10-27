import type { ReactNode } from 'react';
import { cn } from '@/core/utils/cn';

/** Semantic tones map onto the two brand colours; danger is the single exception. */
export type Tone = 'success' | 'warning' | 'info' | 'neutral' | 'danger' | 'accent';

const TONES: Record<Tone, { pill: string; dot: string }> = {
  success: { pill: 'bg-forest-50 text-forest-800 border-forest-100', dot: 'bg-forest-600' },
  info: { pill: 'bg-forest-100 text-forest-900 border-forest-100', dot: 'bg-forest-700' },
  warning: { pill: 'bg-wheat-50 text-ink border-wheat-100', dot: 'bg-wheat-500' },
  accent: { pill: 'bg-wheat-100 text-forest-950 border-wheat-300/60', dot: 'bg-wheat-600' },
  neutral: { pill: 'bg-canvas text-muted border-line', dot: 'bg-muted' },
  danger: { pill: 'bg-danger-tint text-danger border-danger/20', dot: 'bg-danger' },
};


export interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
  dot?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

export function Badge({ tone = 'neutral', children, dot = false, size = 'md', className }: BadgeProps) {
  const t = TONES[tone];
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-pill border font-medium',
        size === 'sm' ? 'h-5 px-2 text-xs' : 'h-6 px-2.5 text-sm',
        t.pill,
        className,
      )}
    >
      {dot && <span className={cn('h-1.5 w-1.5 rounded-full', t.dot)} aria-hidden />}
      {children}
    </span>
  );
}

/** Badge with a status dot; use for workflow states (draft, submitted, in build...). */
export function StatusPill(props: Omit<BadgeProps, 'dot'>) {
  return <Badge {...props} dot />;
}

/** Variant of StatusPill for dark surfaces such as the sidebar. */
export function StatusPillOnDark({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'accent' | 'neutral' }) {
  return (
    <span
      className={cn(
        'inline-flex h-5 shrink-0 items-center whitespace-nowrap rounded-pill border px-2 text-xs font-medium',
        tone === 'accent' ? 'border-wheat-500/40 bg-wheat-500/15 text-wheat-300' : 'border-white/10 bg-white/5 text-forest-100/80',
      )}
    >
      {children}
    </span>
  );
}
