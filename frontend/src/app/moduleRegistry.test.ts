import { describe, expect, it } from 'vitest';
import { findModuleByPath, MODULES, PIPELINE, ROUTABLE_MODULES, statusLabel } from './moduleRegistry';

describe('moduleRegistry', () => {
  it('has eight modules with unique numbers 1 to 8 in order', () => {
    expect(MODULES).toHaveLength(8);
    expect(MODULES.map((m) => m.number)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
  });

  it('has unique paths, folders and API prefixes', () => {
    for (const key of ['path', 'folder', 'apiPrefix', 'name'] as const) {
      const values = MODULES.map((m) => m[key]);
      expect(new Set(values).size).toBe(values.length);
    }
  });

  it('matches the fixed names and routes', () => {
    expect(MODULES.map((m) => [m.name, m.path])).toEqual([
      ['Home', '/'],
      ['Register Farmer', '/register'],
      ['Fieldbook', '/fieldbook'],
      ['Harvest Radar', '/radar'],
      ['Deliveries', '/deliveries'],
      ['Heap', '/heaps'],
      ['QR Tracing', '/qr'],
      ['Settings', '/settings'],
    ]);
    for (const m of MODULES) expect(m.folder).toBe(`module_${m.number}`);
  });

  it('gives every module a page, Settings included', () => {
    const settings = MODULES.find((m) => m.number === 8);
    expect(settings?.status).toBe('active');
    expect(typeof settings?.loader).toBe('function');
    expect(ROUTABLE_MODULES.map((m) => m.number)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    for (const m of ROUTABLE_MODULES) expect(typeof m.loader).toBe('function');
  });

  it('orders the pipeline from Register Farmer to QR Tracing', () => {
    expect(PIPELINE.map((m) => m.number)).toEqual([2, 3, 4, 5, 6, 7]);
    expect(PIPELINE.map((m) => m.pipelineStage)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it('labels status by build order', () => {
    // Every module is built, so no pill is left anywhere in the sidebar.
    for (const m of MODULES) expect(statusLabel(m)).toBeNull();
    expect(statusLabel({ number: 4, status: 'active' })).toBeNull();
    expect(statusLabel({ number: 8, status: 'deferred' })).toBe('Coming later');
  });

  it('finds modules by path', () => {
    expect(findModuleByPath('/')?.number).toBe(1);
    expect(findModuleByPath('/register/new')?.number).toBe(2);
    expect(findModuleByPath('/qr')?.number).toBe(7);
    expect(findModuleByPath('/unknown')).toBeUndefined();
  });
});
