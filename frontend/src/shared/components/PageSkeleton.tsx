import { Skeleton } from '@/design-system/components/Skeleton';

/** Loading state while a lazy module page downloads. */
export function PageSkeleton() {
  return (
    <div className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8" aria-busy="true">
      <span className="sr-only">Loading page</span>
      <Skeleton className="h-6 w-56" shape="block" />
      <Skeleton className="mt-3 w-96 max-w-full" />
      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-28" shape="block" />
        ))}
      </div>
      <Skeleton className="mt-6 h-64" shape="block" />
    </div>
  );
}
