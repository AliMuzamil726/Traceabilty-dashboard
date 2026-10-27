import { ArrowLeft, ChevronRight } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/core/utils/cn';

export interface Crumb {
  label: string;
  to?: string;
}

export interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  breadcrumb?: Crumb[];
  className?: string;
}

export function Breadcrumb({ items, className }: { items: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={className}>
      <ol className="flex flex-wrap items-center gap-1 text-sm text-muted">
        {items.map((c, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${c.label}-${i}`} className="flex items-center gap-1">
              {c.to && !last ? (
                <Link to={c.to} className="rounded-sm hover:text-forest-800">
                  {c.label}
                </Link>
              ) : (
                <span aria-current={last ? 'page' : undefined} className={cn(last && 'text-ink')}>
                  {c.label}
                </span>
              )}
              {!last && <ChevronRight className="h-3.5 w-3.5" aria-hidden />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/**
 * Pages above this one in the breadcrumb become a single back button to the nearest one.
 * The dashboard is left out: the sidebar and the top bar's back button already reach it.
 */
function BackLink({ items }: { items: Crumb[] }) {
  const parent = [...items.slice(0, -1)].reverse().find((c) => c.to && c.to !== '/');
  if (!parent?.to) return null;
  return (
    <Link
      to={parent.to}
      className="mb-3 inline-flex h-8 items-center gap-1.5 rounded-control border border-line bg-surface px-3 text-sm font-medium text-ink transition-colors duration-fast ease-brand hover:bg-forest-50"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden />
      {parent.label}
    </Link>
  );
}

/**
 * Page title and actions. `subtitle` is accepted for compatibility but no longer shown:
 * pages carry their title only.
 */
export function PageHeader({ title, actions, breadcrumb, className }: PageHeaderProps) {
  return (
    <header className={cn('flex flex-wrap items-end justify-between gap-4', className)}>
      <div className="min-w-0">
        {breadcrumb && breadcrumb.length > 0 && <BackLink items={breadcrumb} />}
        <h1 className="text-xl font-semibold tracking-[-0.01em] text-ink">{title}</h1>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
