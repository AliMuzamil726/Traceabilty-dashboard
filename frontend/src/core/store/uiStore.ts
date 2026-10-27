import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

interface UiState {
  sidebarCollapsed: boolean;
  mobileNavOpen: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setMobileNavOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      mobileNavOpen: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setMobileNavOpen: (open) => set({ mobileNavOpen: open }),
    }),
    {
      name: 'sawie.ui',
      storage: createJSONStorage(() => localStorage),
      version: 1,
      // Only the collapse preference is remembered; the mobile drawer always starts closed.
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed }),
    },
  ),
);
