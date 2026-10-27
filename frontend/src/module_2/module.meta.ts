import { UserPlus } from 'lucide-react';
import type { ModuleMeta } from '@/shared/types';

/** Module 2: Register Farmer. Mirrors backend/module_2/meta.py. */
export const meta: ModuleMeta = {
  number: 2,
  name: 'Register Farmer',
  folder: 'module_2',
  path: '/register',
  apiPrefix: '/api/v1/register',
  status: 'active',
  buildOrder: 1,
  purpose: 'Register farmers and map their fields.',
  icon: UserPlus,
  pipelineStage: 1,
};
