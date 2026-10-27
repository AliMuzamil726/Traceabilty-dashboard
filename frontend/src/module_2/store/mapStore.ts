import { create } from 'zustand';
import type { BaseLayerId } from '../map/tileLayers';

/** What the officer is doing with the map right now. */
export type MapTool = 'idle' | 'draw' | 'edit' | 'pin';

interface MapUiState {
  tool: MapTool;
  baseLayer: BaseLayerId;
  showLabels: boolean;
  /** Show every other field in the database as context under the drawing. */
  showAllFields: boolean;
  /** Field whose row and shape are highlighted, chosen from the left rail. */
  selectedFieldId: string | null;
  setTool: (tool: MapTool) => void;
  setBaseLayer: (layer: BaseLayerId) => void;
  toggleLabels: () => void;
  toggleAllFields: () => void;
  selectField: (fieldId: string | null) => void;
  reset: () => void;
}

const INITIAL = {
  tool: 'idle' as MapTool,
  baseLayer: 'satellite' as BaseLayerId,
  showLabels: false,
  showAllFields: true,
  selectedFieldId: null,
};

/**
 * Map chrome only. Nothing here is persisted: a map tool left armed from a previous
 * visit would surprise the officer, and the field data itself lives in TanStack Query.
 */
export const useMapStore = create<MapUiState>()((set) => ({
  ...INITIAL,
  setTool: (tool) => set({ tool }),
  setBaseLayer: (baseLayer) => set({ baseLayer }),
  toggleLabels: () => set((s) => ({ showLabels: !s.showLabels })),
  toggleAllFields: () => set((s) => ({ showAllFields: !s.showAllFields })),
  selectField: (selectedFieldId) => set({ selectedFieldId }),
  reset: () => set(INITIAL),
}));
