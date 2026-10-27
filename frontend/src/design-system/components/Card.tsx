import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/core/utils/cn';

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: 'section' | 'div' | 'article';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  elevated?: boolean;
}

const PADDING = { none: '', sm: 'p-3', md: 'p-4', lg: 'p-5' } as const;

export function Card({ as: Tag = 'section', padding = 'md', elevated, className, ...rest }: CardProps) {
  return (
    <Tag
      className={cn('rounded-card border border-line bg-surface transition-shadow duration-base', elevated ? 'shadow-2' : 'shadow-1', PADDING[padding], className)}
      {...rest}
    />
  );
}

export interface SectionHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  as?: 'h2' | 'h3';
  className?: string;
  id?: string;
}

export function SectionHeader({ title, actions, as: Heading = 'h2', className, id }: SectionHeaderProps) {
  return (
    <div className={cn('flex flex-wrap items-start justify-between gap-x-3 gap-y-1 sm:flex-nowrap', className)}>
      <div className="min-w-0">
        <Heading id={id} className="text-md font-semibold text-ink">
          {title}
        </Heading>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
