import { afterEach, describe, expect, it, vi } from 'vitest';
import { useOfficerStore } from '@/core/store/officerStore';
import { api, buildUrl } from './client';
import { ApiError } from './errors';

afterEach(() => {
  vi.restoreAllMocks();
  useOfficerStore.getState().clearOfficer();
});

describe('api client', () => {
  it('builds URLs and drops empty query values', () => {
    expect(buildUrl('/v1/master/crop', { country: 'PK', crop: undefined, q: '' })).toBe('/api/v1/master/crop?country=PK');
  });

  it('sends the acting officer header', async () => {
    useOfficerStore.getState().setOfficer('officer-123');
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
    await api.get('/v1/officers/me');
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((init.headers as Record<string, string>)['X-Officer-Id']).toBe('officer-123');
  });

  it('turns the error envelope into ApiError with field errors', async () => {
    const body = {
      error: { code: 'validation_error', message: 'Invalid.', details: { fields: [{ field: 'page', location: 'query', message: 'Too small', type: 'x' }] } },
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(body), { status: 422 }));
    const error = await api.get('/v1/officers').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe('validation_error');
    expect((error as ApiError).fieldErrors).toEqual({ page: 'Too small' });
  });

  it('clears a stale officer id', async () => {
    useOfficerStore.getState().setOfficer('gone');
    const body = { error: { code: 'officer_not_found', message: 'x', details: null } };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(body), { status: 401 }));
    await expect(api.get('/v1/officers/me')).rejects.toBeInstanceOf(ApiError);
    expect(useOfficerStore.getState().officerId).toBeNull();
  });

  it('reports network failures', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('fail'));
    const error = (await api.get('/health').catch((e: unknown) => e)) as ApiError;
    expect(error.isNetwork).toBe(true);
  });
});
