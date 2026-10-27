import { Home } from 'lucide-react';
import type { ModuleMeta } from '@/shared/types';

/** Module 1: Home (formerly Dashboard). Mirrors backend/module_1/meta.py. */
export const meta: ModuleMeta = {
  number: 1,
  name: 'Home',
  folder: 'module_1',
  path: '/',
  apiPrefix: '/api/v1/dashboard',
  status: 'active',
  buildOrder: 7,
  purpose: 'Programme overview that reads from every other module.',
  icon: Home,
  pipelineStage: null,
};
