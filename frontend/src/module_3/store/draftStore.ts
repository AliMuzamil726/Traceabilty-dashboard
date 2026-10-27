import { create } from 'zustand';
import type { EntryData } from '../api/types';

/** Key of one draft: a step's single form, or one repeatable entry ("new" when unsaved). */
export function draftKey(bookId: string, stepKey: string, entry: number | 'single' | 'new' = 'single'): string {
  return `${bookId}:${stepKey}:${entry}`;
}

interface DraftState {
  /** Unsaved values per step (or per entry), so moving between steps keeps what was typed. */
  drafts: Record<string, EntryData>;
  setDraft: (key: string, values: EntryData) => void;
  clearDraft: (key: string) => void;
  clearBook: (bookId: string) => void;
}

export const useDraftStore = create<DraftState>()((set) => ({
  drafts: {},
  setDraft: (key, values) => set((s) => ({ drafts: { ...s.drafts, [key]: values } })),
  clearDraft: (key) =>
    set((s) => {
      const { [key]: _gone, ...rest } = s.drafts;
      return { drafts: rest };
    }),
  clearBook: (bookId) =>
    set((s) => ({
      drafts: Object.fromEntries(Object.entries(s.drafts).filter(([k]) => !k.startsWith(`${bookId}:`))),
    })),
}));

export function hasDraftsFor(bookId: string): boolean {
  return Object.keys(useDraftStore.getState().drafts).some((k) => k.startsWith(`${bookId}:`));
}
