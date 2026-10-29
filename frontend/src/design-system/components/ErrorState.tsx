import { AlertTriangle } from 'lucide-react';
import { Button } from './Button';
import { EmptyState } from './EmptyState';

export interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  compact?: boolean;
}

/** A failed read is not an empty screen: say so and offer the retry. */
export function ErrorState({
  title = 'This could not be loaded',
  description,
  onRetry,
  compact,
}: ErrorStateProps) {
  return (
    <EmptyState
      compact={compact}
      icon={<AlertTriangle />}
      title={title}
      description={description}
      action={
        onRetry && (
          <Button size="sm" variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        )
      }
    />
  );
}
