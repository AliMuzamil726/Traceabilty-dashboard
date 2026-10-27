import { Layers } from 'lucide-react';
import type { ModuleMeta } from '@/shared/types';

/** Module 6: Heap. Mirrors backend/module_6/meta.py. */
export const meta: ModuleMeta = {
  number: 6,
  name: 'Heap',
  folder: 'module_6',
  path: '/heaps',
  apiPrefix: '/api/v1/heaps',
  status: 'active',
  buildOrder: 5,
  purpose: 'Group deliveries into a heap (cotton) or batch (hemp) and produce bales.',
  icon: Layers,
  pipelineStage: 5,
};
