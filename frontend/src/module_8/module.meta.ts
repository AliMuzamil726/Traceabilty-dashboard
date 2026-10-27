import { Settings } from 'lucide-react';
import type { ModuleMeta } from '@/shared/types';

/** Module 8: Settings. Mirrors backend/module_8/meta.py. */
export const meta: ModuleMeta = {
  number: 8,
  name: 'Settings',
  folder: 'module_8',
  path: '/settings',
  apiPrefix: '/api/v1/settings',
  status: 'active',
  buildOrder: 8,
  purpose:
    'Administer people, lists, locations, parameters, the audit log and backups.',
  icon: Settings,
  pipelineStage: null,
};
