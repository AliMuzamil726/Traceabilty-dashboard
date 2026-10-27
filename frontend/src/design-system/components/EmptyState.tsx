import type { ReactNode } from 'react';
import { cn } from '@/core/utils/cn';

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}

/** An empty screen is an invitation to act: say what is missing and how to add it. */
export function EmptyState({ icon, title, description, action, className, compact }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center text-center', compact ? 'gap-2 py-8' : 'gap-3 py-14', className)}>
      {icon && (
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-forest-50 text-forest-600 ring-4 ring-forest-50/50 [&>svg]:h-5 [&>svg]:w-5" aria-hidden>
          {icon}
        </span>
      )}
      <p className="text-md font-semibold text-ink">{title}</p>
      {description && <p className="max-w-[46ch] text-base text-muted">{description}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
