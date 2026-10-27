import { cn } from '@/core/utils/cn';

export interface SkeletonProps {
  className?: string;
  /** Rounded pill shape for text lines, card shape for blocks. */
  shape?: 'line' | 'block' | 'circle';
}

/** Loading placeholder with a soft shimmer (disabled under reduced motion). */
export function Skeleton({ className, shape = 'line' }: SkeletonProps) {
  return (
    <span
      aria-hidden
      className={cn(
        'relative block overflow-hidden bg-line/70',
        shape === 'line' && 'h-3 rounded-pill',
        shape === 'block' && 'rounded-control',
        shape === 'circle' && 'rounded-full',
        "before:absolute before:inset-0 before:-translate-x-full before:animate-shimmer before:bg-gradient-to-r before:from-transparent before:via-white/70 before:to-transparent before:content-['']",
        className,
      )}
    />
  );
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <span className={cn('flex flex-col gap-2', className)} aria-hidden>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={i === lines - 1 ? 'w-2/3' : 'w-full'} />
      ))}
    </span>
  );
}
