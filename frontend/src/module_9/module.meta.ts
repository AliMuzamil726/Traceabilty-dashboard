import { Scale } from 'lucide-react';
import type { ModuleMeta } from '@/shared/types';

/** Module 9: Gate Reception. Mirrors backend/module_9/meta.py. */
export const meta: ModuleMeta = {
  number: 9,
  name: 'Gate Reception',
  folder: 'module_9',
  path: '/gate',
  apiPrefix: '/api/v1/gate',
  status: 'active',
  buildOrder: 9,
  purpose:
    'Record the arrival of in-transit deliveries at the ginner or processor gate: weighbridge reading, moisture check, vehicle inspection and officer sign-off.',
  icon: Scale,
  pipelineStage: null,
};
