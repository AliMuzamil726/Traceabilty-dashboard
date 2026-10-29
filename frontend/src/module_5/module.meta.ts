import { Truck } from 'lucide-react';
import type { ModuleMeta } from '@/shared/types';

/** Module 5: Deliveries (Schedule → Dispatch → Delivered). Mirrors backend/module_5/meta.py. */
export const meta: ModuleMeta = {
  number: 5,
  name: 'Deliveries',
  folder: 'module_5',
  path: '/deliveries',
  apiPrefix: '/api/v1/deliveries',
  status: 'active',
  buildOrder: 4,
  purpose:
    'Schedule pickups, dispatch loads in transit, and receive them at the ginner or processor gate.',
  icon: Truck,
  pipelineStage: 4,
};
