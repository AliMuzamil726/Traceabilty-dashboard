import { Radar } from 'lucide-react';
import type { ModuleMeta } from '@/shared/types';

/** Module 4: Harvest Radar. Mirrors backend/module_4/meta.py. */
export const meta: ModuleMeta = {
  number: 4,
  name: 'Harvest Radar',
  folder: 'module_4',
  path: '/radar',
  apiPrefix: '/api/v1/radar',
  status: 'active',
  buildOrder: 3,
  purpose: 'Shows which fields are approaching harvest and ready for pickup.',
  icon: Radar,
  pipelineStage: 3,
};
