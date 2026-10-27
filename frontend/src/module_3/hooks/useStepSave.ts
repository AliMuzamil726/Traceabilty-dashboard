import { useMutation } from '@tanstack/react-query';
import { toApiError } from '@/core/api/errors';
import { fieldbookApi } from '../api/client';
import type { Book, EntryData, Issue } from '../api/types';
import { useStaleHandler, useStoreBook } from './useFieldbook';

export interface SaveArgs {
  stepKey: string;
  data: EntryData;
  /** Single step: omit. Repeatable step: 'new' adds an entry, a number updates one. */
  entry?: number | 'new';
}

export interface SaveOutcome {
  ok: boolean;
  book?: Book;
  warnings: Issue[];
  fieldErrors: Record<string, string>;
  message?: string;
}

/**
 * Saves one step or one entry. Field errors come back keyed by field for the form to
 * show; a stale or locked book is reloaded and reported by toast.
 */
export function useStepSave(book: Book | undefined) {
  const store = useStoreBook();
  const stale = useStaleHandler(book?.id ?? '');
  const mutation = useMutation({
    mutationFn: async ({ stepKey, data, entry }: SaveArgs) => {
      if (!book) throw new Error('No fieldbook is open.');
      if (entry === undefined) return fieldbookApi.saveStep(book, stepKey, data);
      if (entry === 'new') return fieldbookApi.addEntry(book, stepKey, data);
      return fieldbookApi.updateEntry(book, stepKey, entry, data);
    },
    onSuccess: (result) => store(result.book),
  });

  const save = async (args: SaveArgs): Promise<SaveOutcome> => {
    try {
      const result = await mutation.mutateAsync(args);
      return { ok: true, book: result.book, warnings: result.warnings, fieldErrors: {} };
    } catch (error) {
      if (stale(error)) return { ok: false, warnings: [], fieldErrors: {} };
      const err = toApiError(error);
      return { ok: false, warnings: [], fieldErrors: err.fieldErrors, message: err.message };
    }
  };

  return { save, saving: mutation.isPending };
}
