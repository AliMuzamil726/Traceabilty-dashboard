import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

interface OfficerState {
  /** Signed-in officer id; null until someone signs in. */
  officerId: string | null;
  /** True after the (placeholder) sign-in screen has been completed. */
  signedIn: boolean;
  setOfficer: (id: string | null) => void;
  signIn: (id: string) => void;
  signOut: () => void;
  clearOfficer: () => void;
}

/**
 * The signed-in officer. Sign-in is a placeholder for now (no password check): the
 * API client reads this on every request and sends it as the X-Officer-Id header.
 */
export const useOfficerStore = create<OfficerState>()(
  persist(
    (set) => ({
      officerId: null,
      signedIn: false,
      setOfficer: (id) => set({ officerId: id }),
      signIn: (id) => set({ officerId: id, signedIn: true }),
      signOut: () => set({ officerId: null, signedIn: false }),
      clearOfficer: () => set({ officerId: null, signedIn: false }),
    }),
    { name: 'sawie.officer', storage: createJSONStorage(() => localStorage), version: 1 },
  ),
);
