import type { ReactNode } from 'react';
import { cn } from '@/core/utils/cn';

export interface KeyValueItem {
  label: string;
  value: ReactNode;
  /** Render the value in JetBrains Mono (IDs, coordinates). */
  mono?: boolean;
}

export interface KeyValueListProps {
  items: KeyValueItem[];
  columns?: 1 | 2;
  className?: string;
}

export function KeyValueList({ items, columns = 1, className }: KeyValueListProps) {
  return (
    <dl className={cn('grid gap-x-6', columns === 2 && 'sm:grid-cols-2', className)}>
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline justify-between gap-4 border-b border-line py-2.5 last:border-b-0">
          <dt className="text-sm text-muted">{item.label}</dt>
          <dd className={cn('text-right text-base text-ink', item.mono && 'mono-id text-sm')}>{item.value ?? '-'}</dd>
        </div>
      ))}
    </dl>
  );
}
