import { create } from 'zustand';

export type ToastTone = 'success' | 'info' | 'warning' | 'error';

export interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  description?: string;
  duration: number;
}

interface ToastState {
  toasts: ToastItem[];
  push: (toast: Omit<ToastItem, 'id' | 'duration'> & { duration?: number }) => number;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: ({ duration = 4500, ...toast }) => {
    const id = nextId++;
    set({ toasts: [...get().toasts, { ...toast, id, duration }].slice(-4) });
    if (duration > 0) window.setTimeout(() => get().dismiss(id), duration);
    return id;
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}));

/** Imperative API: toast.success('Farmer registered'). */
export const toast = {
  success: (title: string, description?: string) => useToastStore.getState().push({ tone: 'success', title, description }),
  info: (title: string, description?: string) => useToastStore.getState().push({ tone: 'info', title, description }),
  warning: (title: string, description?: string) => useToastStore.getState().push({ tone: 'warning', title, description }),
  error: (title: string, description?: string) => useToastStore.getState().push({ tone: 'error', title, description, duration: 7000 }),
};

