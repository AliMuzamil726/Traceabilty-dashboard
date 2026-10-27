import { NotebookPen } from 'lucide-react';
import type { ModuleMeta } from '@/shared/types';

/** Module 3: Fieldbook. Mirrors backend/module_3/meta.py. */
export const meta: ModuleMeta = {
  number: 3,
  name: 'Fieldbook',
  folder: 'module_3',
  path: '/fieldbook',
  apiPrefix: '/api/v1/fieldbook',
  status: 'active',
  buildOrder: 2,
  purpose: 'A season diary for each field, step by step, locked on submit.',
  icon: NotebookPen,
  pipelineStage: 2,
};
