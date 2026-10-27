/**
 * Typed calls to /api/v1/fieldbook. Every write carries the version the editor last saw
 * (X-Fieldbook-Version), so a second officer's stale save is refused rather than lost.
 */

import { api, apiRequest } from '@/core/api/client';
import type {
  Book,
  Crop,
  EntryData,
  FarmerOption,
  FieldSelector,
  FormDefinition,
  OfficerOption,
  SaveResult,
  TimelineItem,
} from './types';

const BASE = '/v1/fieldbook';
export const VERSION_HEADER = 'X-Fieldbook-Version';

function versioned(version: number | undefined): Record<string, string> {
  return version === undefined ? {} : { [VERSION_HEADER]: String(version) };
}

const step = (bookId: string, stepKey: string) => `${BASE}/books/${bookId}/steps/${stepKey}`;

export const fieldbookApi = {
  schema: (crop: Crop, signal?: AbortSignal) =>
    api.get<FormDefinition>(`${BASE}/schemas/${crop}`, undefined, signal),

  officers: (signal?: AbortSignal) =>
    api.get<OfficerOption[]>(`${BASE}/selectors/officers`, undefined, signal),

  farmers: (officerId: string, q: string | undefined, seasonYear: number, signal?: AbortSignal) =>
    api.get<FarmerOption[]>(
      `${BASE}/selectors/farmers`,
      { officer_id: officerId, q, season_year: seasonYear },
      signal,
    ),

  fields: (farmerId: string, seasonYear: number, signal?: AbortSignal) =>
    api.get<FieldSelector>(
      `${BASE}/selectors/fields`,
      { farmer_id: farmerId, season_year: seasonYear },
      signal,
    ),

  open: (fieldId: string, seasonYear: number) =>
    api.post<Book>(`${BASE}/books`, { field_id: fieldId, season_year: seasonYear }),

  get: (bookId: string, signal?: AbortSignal) =>
    api.get<Book>(`${BASE}/books/${bookId}`, undefined, signal),

  remove: (bookId: string) => api.delete<void>(`${BASE}/books/${bookId}`),

  saveStep: (book: Book, stepKey: string, data: EntryData) =>
    apiRequest<SaveResult>(step(book.id, stepKey), {
      method: 'PUT',
      body: { data, crop: book.crop },
      headers: versioned(book.version),
    }),

  addEntry: (book: Book, stepKey: string, data: EntryData) =>
    apiRequest<SaveResult>(`${step(book.id, stepKey)}/entries`, {
      method: 'POST',
      body: { data, crop: book.crop },
      headers: versioned(book.version),
    }),

  updateEntry: (book: Book, stepKey: string, index: number, data: EntryData) =>
    apiRequest<SaveResult>(`${step(book.id, stepKey)}/entries/${index}`, {
      method: 'PUT',
      body: { data, crop: book.crop },
      headers: versioned(book.version),
    }),

  deleteEntry: (book: Book, stepKey: string, index: number) =>
    apiRequest<Book>(`${step(book.id, stepKey)}/entries/${index}`, {
      method: 'DELETE',
      headers: versioned(book.version),
    }),

  setNotApplicable: (book: Book, stepKey: string, notApplicable: boolean) =>
    apiRequest<Book>(`${step(book.id, stepKey)}/not-applicable`, {
      method: 'POST',
      body: { not_applicable: notApplicable, crop: book.crop },
      headers: versioned(book.version),
    }),

  addPhotos: (book: Book, files: File[]) => {
    const form = new FormData();
    for (const file of files) form.append('files', file);
    return apiRequest<Book>(`${BASE}/books/${book.id}/photos`, {
      method: 'POST',
      body: form,
      headers: versioned(book.version),
    });
  },

  deletePhoto: (book: Book, photoId: string) =>
    apiRequest<Book>(`${BASE}/books/${book.id}/photos/${photoId}`, {
      method: 'DELETE',
      headers: versioned(book.version),
    }),

  submit: (book: Book) =>
    apiRequest<Book>(`${BASE}/books/${book.id}/submit`, {
      method: 'POST',
      headers: versioned(book.version),
    }),

  timeline: (bookId: string, signal?: AbortSignal) =>
    api.get<{ items: TimelineItem[] }>(`${BASE}/books/${bookId}/timeline`, undefined, signal),
};

export const fieldbookKeys = {
  all: ['fieldbook'] as const,
  schema: (crop: Crop) => ['fieldbook', 'schema', crop] as const,
  officers: ['fieldbook', 'officers'] as const,
  farmers: (officerId: string | null, q: string, season: number) =>
    ['fieldbook', 'farmers', officerId, q, season] as const,
  fields: (farmerId: string | null, season: number) =>
    ['fieldbook', 'fields', farmerId, season] as const,
  book: (bookId: string) => ['fieldbook', 'book', bookId] as const,
  timeline: (bookId: string) => ['fieldbook', 'book', bookId, 'timeline'] as const,
};
