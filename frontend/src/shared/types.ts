import type { LucideIcon } from 'lucide-react';

export type ModuleStatus = 'active' | 'placeholder' | 'deferred';

/** Identity of one product module. Mirrors backend/module_N/meta.py. */
export interface ModuleMeta {
  number: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;
  name: string;
  folder: `module_${number}`;
  /** Frontend route. */
  path: string;
  /** Backend prefix (informational). */
  apiPrefix: string;
  status: ModuleStatus;
  /** Position in the build plan (Register Farmer is built first). */
  buildOrder: number;
  /** One-line purpose shown on placeholders and tooltips. */
  purpose: string;
  icon: LucideIcon;
  /** Position in the farm-to-bale chain (1-6), or null for Dashboard and Settings. */
  pipelineStage: number | null;
}
