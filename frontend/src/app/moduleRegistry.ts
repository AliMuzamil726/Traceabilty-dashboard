import type { ComponentType } from 'react';
import { meta as m1 } from '@/module_1/module.meta';
import { meta as m2 } from '@/module_2/module.meta';
import { meta as m3 } from '@/module_3/module.meta';
import { meta as m4 } from '@/module_4/module.meta';
import { meta as m5 } from '@/module_5/module.meta';
import { meta as m6 } from '@/module_6/module.meta';
import { meta as m7 } from '@/module_7/module.meta';
import { meta as m8 } from '@/module_8/module.meta';
import type { ModuleMeta } from '@/shared/types';

export type ModuleLoader = () => Promise<{ default: ComponentType }>;

export interface ModuleEntry extends ModuleMeta {
  /** Lazy page loader; null for deferred modules (no page exists). */
  loader: ModuleLoader | null;
}

/**
 * Every module, in sidebar order. Adding a module = add its meta import and an
 * entry here (see README "How to add a new module").
 */
export const MODULES: readonly ModuleEntry[] = [
  { ...m1, loader: () => import('@/module_1') },
  { ...m2, loader: () => import('@/module_2') },
  { ...m3, loader: () => import('@/module_3') },
  { ...m4, loader: () => import('@/module_4') },
  { ...m5, loader: () => import('@/module_5') },
  { ...m6, loader: () => import('@/module_6') },
  { ...m7, loader: () => import('@/module_7') },
  { ...m8, loader: () => import('@/module_8') },
];

/** Modules that have a page (everything except deferred ones). */
export const ROUTABLE_MODULES = MODULES.filter((m) => m.status !== 'deferred' && m.loader !== null);

/** The farm-to-bale chain, in order (Register Farmer to QR Tracing). */
export const PIPELINE = MODULES.filter((m) => m.pipelineStage !== null).sort(
  (a, b) => (a.pipelineStage ?? 0) - (b.pipelineStage ?? 0),
);

export function findModuleByPath(pathname: string): ModuleEntry | undefined {
  if (pathname === '/' || pathname === '') return MODULES.find((m) => m.path === '/');
  return MODULES.filter((m) => m.path !== '/').find((m) => pathname === m.path || pathname.startsWith(`${m.path}/`));
}

/** The placeholder module currently being built: lowest build order not yet active. */
export function moduleInBuild(): ModuleEntry | undefined {
  return [...MODULES]
    .filter((m) => m.status === 'placeholder')
    .sort((a, b) => a.buildOrder - b.buildOrder)[0];
}

export type StatusLabel = 'In build' | 'Planned' | 'Coming later' | null;

/** Pill text for a module: none once active. */
export function statusLabel(entry: Pick<ModuleMeta, 'number' | 'status'>): StatusLabel {
  if (entry.status === 'active') return null;
  if (entry.status === 'deferred') return 'Coming later';
  return moduleInBuild()?.number === entry.number ? 'In build' : 'Planned';
}
