import { QrCode } from 'lucide-react';
import type { ModuleMeta } from '@/shared/types';

/** Module 7: QR Tracing. Mirrors backend/module_7/meta.py. */
export const meta: ModuleMeta = {
  number: 7,
  name: 'QR Tracing',
  folder: 'module_7',
  path: '/qr',
  apiPrefix: '/api/v1/qr',
  status: 'active',
  buildOrder: 6,
  purpose: 'QR-tagged bales traced back to farmers and fields.',
  icon: QrCode,
  pipelineStage: 6,
};
