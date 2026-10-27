import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from '@/design-system/components';
import { toApiError } from '@/core/api/errors';
import { fieldbookApi, fieldbookKeys } from '../api/client';
import type { Book } from '../api/types';

export function useFieldbook(bookId: string | undefined) {
  return useQuery({
    queryKey: fieldbookKeys.book(bookId ?? ''),
    queryFn: ({ signal }) => fieldbookApi.get(bookId as string, signal),
    enabled: Boolean(bookId),
  });
}

export function useTimeline(bookId: string | undefined, version: number | undefined) {
  return useQuery({
    queryKey: [...fieldbookKeys.timeline(bookId ?? ''), version ?? 0],
    queryFn: ({ signal }) => fieldbookApi.timeline(bookId as string, signal),
    enabled: Boolean(bookId),
    placeholderData: (previous) => previous,
  });
}

/** Store a fresh book state returned by any write, so every panel updates at once. */
export function useStoreBook() {
  const client = useQueryClient();
  return (book: Book) => {
    client.setQueryData(fieldbookKeys.book(book.id), book);
    void client.invalidateQueries({ queryKey: ['fieldbook', 'farmers'] });
    void client.invalidateQueries({ queryKey: ['fieldbook', 'fields'] });
  };
}

/** A stale save means someone else changed the book: reload it and say so. */
export function useStaleHandler(bookId: string) {
  const client = useQueryClient();
  return (error: unknown): boolean => {
    const err = toApiError(error);
    if (err.code === 'fieldbook_stale' || err.code === 'fieldbook_locked') {
      void client.invalidateQueries({ queryKey: fieldbookKeys.book(bookId) });
      toast.warning(
        err.code === 'fieldbook_locked' ? 'This fieldbook is locked' : 'This fieldbook changed',
        err.code === 'fieldbook_locked'
          ? 'It was submitted and can no longer be edited.'
          : 'Another save happened first. The latest version has been loaded; check your step and save again.',
      );
      return true;
    }
    return false;
  };
}

export function useBookAction<TArgs>(bookId: string, run: (args: TArgs) => Promise<Book>) {
  const store = useStoreBook();
  const stale = useStaleHandler(bookId);
  return useMutation({
    mutationFn: run,
    onSuccess: store,
    onError: (error) => {
      if (!stale(error)) toast.error('That did not work', toApiError(error).message);
    },
  });
}
