import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useBlocker } from 'react-router-dom';
import { ApiError } from '@/core/api/errors';
import { toast } from '@/design-system/components/toastStore';
import { settingsApi, settingsKeys, type AuditQuery } from '../api/client';
import type { Preferences, Setting } from '../api/types';

/** Every declared setting, optionally one group at a time. */
export function useSettingsRegistry(group?: string) {
  return useQuery({
    queryKey: settingsKeys.registry(group),
    queryFn: ({ signal }) => settingsApi.registry(group, signal),
  });
}

/**
 * Save one setting, with optimistic concurrency.
 *
 * A save sends the version the screen loaded. If another administrator has saved since,
 * the server refuses with 409 and the current value, which the caller shows rather than
 * overwriting their change.
 */
export function useSaveSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      key,
      value,
      version,
      reason,
    }: {
      key: string;
      value: unknown;
      version?: number;
      reason?: string;
    }) => settingsApi.setValue(key, value, version, reason),
    onSuccess: (saved: Setting) => {
      toast.success('Setting saved', saved.label);
      void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.code === 'stale_version') {
        toast.error(
          'Someone else saved this first',
          'Reload to see the current value, then make your change again.',
        );
        return;
      }
      toast.error('Could not save', error instanceof ApiError ? error.message : 'Please try again.');
    },
  });
}

export function useResetSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => settingsApi.resetValue(key),
    onSuccess: (saved: Setting) => {
      toast.success('Back to the default', saved.label);
      void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
    },
  });
}

export function useSettingHistory(key?: string, enabled = true) {
  return useQuery({
    queryKey: settingsKeys.history(key),
    queryFn: ({ signal }) => settingsApi.history(key, signal),
    enabled,
  });
}

export function useRestoreSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (historyId: string) => settingsApi.restore(historyId),
    onSuccess: (saved: Setting) => {
      toast.success('Previous value restored', saved.label);
      void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
    },
  });
}

/** Configuration owned by another module (crop clock, deliveries, heaps). */
export function useConfigBlock<T>(block: string) {
  return useQuery({
    queryKey: settingsKeys.config(block),
    queryFn: ({ signal }) => settingsApi.config<T>(block, signal),
  });
}

export function useSaveConfigBlock(block: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      values,
      version,
    }: {
      values: Record<string, unknown>;
      version?: number;
    }) => settingsApi.saveConfig(block, values, version),
    onSuccess: () => {
      toast.success('Saved', 'The change applies to new calculations.');
      void queryClient.invalidateQueries({ queryKey: settingsKeys.all });
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.code === 'stale_version') {
        toast.error(
          'Someone else saved this first',
          'Reload to see the current values, then make your change again.',
        );
        return;
      }
      toast.error('Could not save', error instanceof ApiError ? error.message : 'Please try again.');
    },
  });
}

export function useAuditLog(params: AuditQuery) {
  return useQuery({
    queryKey: settingsKeys.audit(params),
    queryFn: ({ signal }) => settingsApi.audit(params, signal),
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: settingsKeys.preferences,
    queryFn: ({ signal }) => settingsApi.preferences(signal),
    staleTime: 5 * 60_000,
  });
}

export function useSavePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Preferences>) => settingsApi.savePreferences(body),
    onSuccess: (saved) => {
      queryClient.setQueryData(settingsKeys.preferences, saved);
      toast.success('Preferences saved');
    },
  });
}

/**
 * Track a form's dirty state and warn before the change is lost.
 *
 * Returns the current draft, a setter, whether anything changed, and a reset. The
 * browser's own dialog covers a reload or a closed tab; the router blocker covers a
 * move to another page inside the app.
 */
export function useDirtyForm<T extends object>(initial: T | undefined) {
  const [draft, setDraft] = useState<T | undefined>(initial);
  const baseline = useRef<T | undefined>(initial);

  useEffect(() => {
    // A reload from the server replaces the baseline only while the form is clean.
    if (initial && !baseline.current) {
      baseline.current = initial;
      setDraft(initial);
    }
  }, [initial]);

  const dirty = useMemo(() => {
    if (!draft || !baseline.current) return false;
    return JSON.stringify(draft) !== JSON.stringify(baseline.current);
  }, [draft]);

  const changed = useCallback(
    (field: keyof T) => {
      if (!draft || !baseline.current) return false;
      return JSON.stringify(draft[field]) !== JSON.stringify(baseline.current[field]);
    },
    [draft],
  );

  const reset = useCallback((next?: T) => {
    if (next) baseline.current = next;
    setDraft(baseline.current);
  }, []);

  const accept = useCallback((next: T) => {
    baseline.current = next;
    setDraft(next);
  }, []);

  useUnsavedGuard(dirty);

  return { draft, setDraft, dirty, changed, reset, accept };
}

/** Warn before leaving a page with unsaved changes, inside the app and outside it. */
export function useUnsavedGuard(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return undefined;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (blocker.state !== 'blocked') return;
    const leave = window.confirm(
      'You have unsaved changes on this page. Leave without saving them?',
    );
    if (leave) blocker.proceed?.();
    else blocker.reset?.();
  }, [blocker]);

  return blocker;
}
