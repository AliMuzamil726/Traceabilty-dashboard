/** Typed calls to /api/v1/settings. */

import { api, apiRequest, buildUrl } from '@/core/api/client';
import type {
  AlertConfig,
  AuditFacets,
  AuditPage,
  Backup,
  BackupStatus,
  ClockPreview,
  CropConfig,
  DummyData,
  DummyRemoved,
  HistoryEntry,
  ImportReport,
  ListSummary,
  ListValue,
  LocationNode,
  LocationTree,
  MergePreview,
  Office,
  Officer,
  PermissionRow,
  Preferences,
  PublicConfig,
  RenamePreview,
  RestoreResult,
  Setting,
  SettingsPage,
  Site,
  SystemInfo,
  TestResult,
} from './types';

const BASE = '/v1/settings';

/** A CSV body is sent as text, not JSON, so the import routes take it raw. */
function postCsv<T>(path: string, text: string): Promise<T> {
  return apiRequest<T>(path, {
    method: 'POST',
    body: text,
    headers: { 'Content-Type': 'text/csv' },
  });
}

export const settingsApi = {
  // configuration the whole app reads
  publicConfig: (signal?: AbortSignal) => api.get<PublicConfig>(`${BASE}/public`, undefined, signal),

  // generic settings
  registry: (group?: string, signal?: AbortSignal) =>
    api.get<SettingsPage>(`${BASE}/registry`, { group }, signal),
  setValue: (key: string, value: unknown, expectedVersion?: number, reason?: string) =>
    api.put<Setting>(`${BASE}/values/${key}`, {
      value,
      expected_version: expectedVersion ?? null,
      reason: reason ?? null,
    }),
  resetValue: (key: string) => api.delete<Setting>(`${BASE}/values/${key}`),
  history: (key?: string, signal?: AbortSignal) =>
    api.get<HistoryEntry[]>(`${BASE}/history`, { key, limit: 50 }, signal),
  restore: (historyId: string) => api.post<Setting>(`${BASE}/history/${historyId}/restore`),

  // people
  officers: (params: { active?: boolean; office_id?: string; q?: string } = {}, signal?: AbortSignal) =>
    api.get<Officer[]>(`${BASE}/officers`, { ...params }, signal),
  createOfficer: (body: Partial<Officer>) => api.post<Officer>(`${BASE}/officers`, body),
  updateOfficer: (id: string, body: Partial<Officer>) =>
    api.put<Officer>(`${BASE}/officers/${id}`, body),
  setOfficerActive: (id: string, active: boolean) =>
    api.post<Officer>(`${BASE}/officers/${id}/${active ? 'activate' : 'deactivate'}`),
  importOfficers: (text: string, dryRun: boolean) =>
    postCsv<ImportReport>(`${BASE}/officers/import?dry_run=${dryRun}`, text),
  officersCsvUrl: () => buildUrl(`${BASE}/officers/export.csv`),

  offices: (signal?: AbortSignal) => api.get<Office[]>(`${BASE}/offices`, undefined, signal),
  createOffice: (body: Partial<Office>) => api.post<Office>(`${BASE}/offices`, body),
  updateOffice: (id: string, body: Partial<Office>) =>
    api.put<Office>(`${BASE}/offices/${id}`, body),

  // sites
  sites: (params: { crop?: string; active?: boolean } = {}, signal?: AbortSignal) =>
    api.get<Site[]>(`${BASE}/sites`, { ...params }, signal),
  createSite: (body: Partial<Site>) => api.post<Site>(`${BASE}/sites`, body),
  updateSite: (id: string, body: Partial<Site>) => api.put<Site>(`${BASE}/sites/${id}`, body),
  deleteSite: (id: string) => api.delete<void>(`${BASE}/sites/${id}`),

  // lists
  lists: (signal?: AbortSignal) => api.get<ListSummary[]>(`${BASE}/lists`, undefined, signal),
  listValues: (key: string, signal?: AbortSignal) =>
    api.get<ListValue[]>(`${BASE}/lists/${key}/values`, undefined, signal),
  addListValue: (key: string, body: { label: string; value?: string; crop?: string | null }) =>
    api.post<ListValue>(`${BASE}/lists/${key}/values`, body),
  updateListValue: (key: string, id: string, body: { label?: string; active?: boolean }) =>
    api.put<ListValue>(`${BASE}/lists/${key}/values/${id}`, body),
  deleteListValue: (key: string, id: string) =>
    api.delete<void>(`${BASE}/lists/${key}/values/${id}`),
  reorderList: (key: string, ids: string[]) =>
    api.post<ListValue[]>(`${BASE}/lists/${key}/reorder`, { ids }),
  importList: (key: string, text: string, dryRun: boolean) =>
    postCsv<ImportReport>(`${BASE}/lists/${key}/import?dry_run=${dryRun}`, text),
  listCsvUrl: (key: string) => buildUrl(`${BASE}/lists/${key}/export.csv`),

  // locations
  locationTree: (country: string, signal?: AbortSignal) =>
    api.get<LocationTree>(`${BASE}/locations/tree`, { country }, signal),
  createLocation: (body: { name: string; level: string; parent_id?: string | null; country: string }) =>
    api.post<LocationNode>(`${BASE}/locations`, body),
  updateLocation: (id: string, body: { name?: string; active?: boolean }) =>
    api.put<{ id: string; name?: string; farmers_updated?: number }>(`${BASE}/locations/${id}`, body),
  renamePreview: (id: string, name: string) =>
    api.get<RenamePreview>(`${BASE}/locations/${id}/rename-preview`, { name }),
  deleteLocation: (id: string) => api.delete<void>(`${BASE}/locations/${id}`),
  mergePreview: (sourceId: string, targetId: string) =>
    api.post<MergePreview>(`${BASE}/locations/merge-preview`, {
      source_id: sourceId,
      target_id: targetId,
    }),
  merge: (sourceId: string, targetId: string) =>
    api.post<{ farmers_updated: number }>(`${BASE}/locations/merge`, {
      source_id: sourceId,
      target_id: targetId,
    }),
  importLocations: (text: string, dryRun: boolean) =>
    postCsv<ImportReport>(`${BASE}/locations/import?dry_run=${dryRun}`, text),
  locationsCsvUrl: (country: string) =>
    buildUrl(`${BASE}/locations/export.csv`, { country }),

  // configuration owned by other modules
  config: <T = CropConfig>(block: string, signal?: AbortSignal) =>
    api.get<T>(`${BASE}/config/${block}`, undefined, signal),
  alerts: (signal?: AbortSignal) => api.get<AlertConfig>(`${BASE}/config/alerts`, undefined, signal),
  saveConfig: (block: string, values: Record<string, unknown>, expectedVersion?: number) =>
    api.put<CropConfig>(`${BASE}/config/${block}`, {
      values,
      expected_version: expectedVersion ?? null,
    }),
  previewClock: (values: Record<string, unknown>) =>
    api.post<ClockPreview>(`${BASE}/config/clock/preview`, { values }),

  // permissions, audit, backups, system
  permissions: (signal?: AbortSignal) =>
    api.get<PermissionRow[]>(`${BASE}/permissions`, undefined, signal),
  audit: (params: Record<string, string | number | undefined>, signal?: AbortSignal) =>
    api.get<AuditPage>(`${BASE}/audit`, { ...params }, signal),
  auditFacets: (signal?: AbortSignal) =>
    api.get<AuditFacets>(`${BASE}/audit/facets`, undefined, signal),
  auditCsvUrl: (params: Record<string, string | number | undefined>) =>
    buildUrl(`${BASE}/audit/export.csv`, { ...params }),

  backups: (signal?: AbortSignal) => api.get<Backup[]>(`${BASE}/backups`, undefined, signal),
  backupStatus: (signal?: AbortSignal) =>
    api.get<BackupStatus>(`${BASE}/backups/status`, undefined, signal),
  createBackup: (note?: string) => api.post<Backup>(`${BASE}/backups`, { note: note ?? null }),
  deleteBackup: (id: string) => api.delete<void>(`${BASE}/backups/${id}`),
  restoreBackup: (id: string, confirm: string) =>
    api.post<RestoreResult>(`${BASE}/backups/${id}/restore`, { confirm }),
  backupDownloadUrl: (id: string) => buildUrl(`${BASE}/backups/${id}/download`),

  system: (signal?: AbortSignal) => api.get<SystemInfo>(`${BASE}/system`, undefined, signal),
  dummyData: (signal?: AbortSignal) => api.get<DummyData>(`${BASE}/system/dummy`, undefined, signal),
  removeDummy: () => api.post<DummyRemoved>(`${BASE}/system/dummy/remove`),

  testUrl: (url: string) => api.post<TestResult>(`${BASE}/qr/test-url`, { url }),
  testTiles: (provider: string, customUrl?: string) =>
    api.post<TestResult>(`${BASE}/map/test-tiles`, {
      provider,
      custom_url: customUrl ?? null,
    }),

  // preferences (every officer)
  preferences: (signal?: AbortSignal) =>
    api.get<Preferences>(`${BASE}/me/preferences`, undefined, signal),
  savePreferences: (body: Partial<Preferences>) =>
    api.put<Preferences>(`${BASE}/me/preferences`, body),
};

export const settingsKeys = {
  all: ['settings'] as const,
  public: ['settings', 'public'] as const,
  registry: (group?: string) => ['settings', 'registry', group ?? null] as const,
  history: (key?: string) => ['settings', 'history', key ?? null] as const,
  officers: (params: object) => ['settings', 'officers', params] as const,
  offices: ['settings', 'offices'] as const,
  sites: (params: object) => ['settings', 'sites', params] as const,
  lists: ['settings', 'lists'] as const,
  listValues: (key: string) => ['settings', 'lists', key] as const,
  locations: (country: string) => ['settings', 'locations', country] as const,
  config: (block: string) => ['settings', 'config', block] as const,
  permissions: ['settings', 'permissions'] as const,
  audit: (params: object) => ['settings', 'audit', params] as const,
  auditFacets: ['settings', 'audit', 'facets'] as const,
  backups: ['settings', 'backups'] as const,
  backupStatus: ['settings', 'backups', 'status'] as const,
  system: ['settings', 'system'] as const,
  dummy: ['settings', 'dummy'] as const,
  preferences: ['settings', 'preferences'] as const,
};

export type AuditQuery = Record<string, string | number | undefined>;
