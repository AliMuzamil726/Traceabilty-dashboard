import { RotateCcw, TriangleAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { toApiError } from '@/core/api/errors';
import { cn } from '@/core/utils/cn';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { Skeleton } from '@/design-system/components/Skeleton';

export interface SectionCardProps {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  /** Height of the skeleton, so the page does not jump as sections arrive. */
  skeletonHeight?: string;
  children?: ReactNode;
  className?: string;
}

/**
 * One section of the dashboard, with its own loading, error and retry.
 *
 * Sections are read independently, so one that cannot be read must not take the page
 * with it: this shows the failure inside the section's own frame and offers to try
 * that section again.
 */
export function SectionCard({
  id,
  title,
  description,
  actions,
  loading = false,
  error,
  onRetry,
  skeletonHeight = 'h-56',
  children,
  className,
}: SectionCardProps) {
  return (
    <Card as="section" aria-labelledby={id} padding="md" className={cn('min-w-0', className)}>
      <SectionHeader id={id} title={title} description={description} actions={actions} />
      <div className="mt-4">
        {error ? (
          <SectionError error={error} onRetry={onRetry} />
        ) : loading ? (
          <Skeleton className={cn('w-full', skeletonHeight)} shape="block" />
        ) : (
          children
        )}
      </div>
    </Card>
  );
}

export function SectionError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const problem = toApiError(error);
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-control border border-line bg-canvas p-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="flex items-start gap-2 text-base text-ink">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-wheat-600" aria-hidden />
        <span>
          This section could not be loaded. {problem.message}
        </span>
      </p>
      {onRetry && (
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          leftIcon={<RotateCcw className="h-4 w-4" />}
        >
          Try again
        </Button>
      )}
    </div>
  );
}
