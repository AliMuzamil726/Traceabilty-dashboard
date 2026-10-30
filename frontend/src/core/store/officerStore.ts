import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

interface OfficerState {
  /** Signed-in officer id; null until someone signs in. */
  officerId: string | null;
  /** Signed session token sent as `Authorization: Bearer`; null until sign-in. */
  token: string | null;
  /** True after the sign-in screen has been completed. */
  signedIn: boolean;
  setOfficer: (id: string | null) => void;
  signIn: (id: string, token: string) => void;
  signOut: () => void;
  clearOfficer: () => void;
}

/**
 * The signed-in officer. The API client reads this on every request: the token proves
 * who is acting, the officer id is sent along for development convenience.
 */
export const useOfficerStore = create<OfficerState>()(
  persist(
    (set) => ({
      officerId: null,
      token: null,
      signedIn: false,
      // Switching officer is a development tool; it does not mint a new token.
      setOfficer: (id) => set({ officerId: id }),
      signIn: (id, token) => set({ officerId: id, token, signedIn: true }),
      signOut: () => set({ officerId: null, token: null, signedIn: false }),
      clearOfficer: () => set({ officerId: null, token: null, signedIn: false }),
    }),
    {
      name: 'sawie.officer',
      storage: createJSONStorage(() => localStorage),
      version: 2,
      // Version 1 stored no token, so those sessions must sign in again.
      migrate: (persisted, version) =>
        version < 2
          ? ({ officerId: null, token: null, signedIn: false } as OfficerState)
          : (persisted as OfficerState),
    },
  ),
);
