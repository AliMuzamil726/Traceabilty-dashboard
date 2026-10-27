/**
 * Typed calls to /api/v1/register. Every request goes through the shared api client,
 * which attaches the acting officer and turns failures into ApiError.
 */

import { api, apiRequest } from '@/core/api/client';
import type { Page } from '@/core/api/types';
import type {
  Crop,
  Farmer,
  FarmerFields,
  FarmerInput,
  FarmerListItem,
  FarmerLookup,
  FarmerProfile,
  FarmerSaved,
  Field,
  GeometryValidation,
  LocationList,
  MapFields,
  PolygonGeometry,
  PostcodeLocation,
} from './types';

const BASE = '/v1/register';

export interface FarmerSearchParams {
  q?: string;
  crop?: Crop | '';
  field_office_id?: string;
  page?: number;
  page_size?: number;
}

export const registerApi = {
  listFarmers: (params: FarmerSearchParams, signal?: AbortSignal) =>
    api.get<Page<FarmerListItem>>(`${BASE}/farmers`, { ...params }, signal),

  lookupFarmer: (idNumber: string, crop: Crop, signal?: AbortSignal) =>
    api.get<FarmerLookup>(`${BASE}/farmers/lookup`, { id_number: idNumber, crop }, signal),

  getFarmer: (farmerId: string, signal?: AbortSignal) =>
    api.get<Farmer>(`${BASE}/farmers/${farmerId}`, undefined, signal),

  getFarmerProfile: (farmerId: string, signal?: AbortSignal) =>
    api.get<FarmerProfile>(`${BASE}/farmers/${farmerId}/profile`, undefined, signal),

  createFarmer: (body: FarmerInput) => api.post<FarmerSaved>(`${BASE}/farmers`, body),

  updateFarmer: (farmerId: string, body: FarmerInput) =>
    api.put<FarmerSaved>(`${BASE}/farmers/${farmerId}`, body),

  listFarmerFields: (farmerId: string, signal?: AbortSignal) =>
    api.get<FarmerFields>(`${BASE}/farmers/${farmerId}/fields`, undefined, signal),

  createField: (farmerId: string, body: { geometry: PolygonGeometry; pin_lat?: number | null; pin_lng?: number | null }) =>
    api.post<Field>(`${BASE}/farmers/${farmerId}/fields`, body),

  updateField: (
    fieldId: string,
    body: { geometry?: PolygonGeometry | null; pin_lat?: number | null; pin_lng?: number | null },
  ) => api.put<Field>(`${BASE}/fields/${fieldId}`, body),

  deleteField: (fieldId: string) => api.delete<void>(`${BASE}/fields/${fieldId}`),

  validateGeometry: (
    body: {
      farmer_id: string;
      geometry: PolygonGeometry;
      pin_lat?: number | null;
      pin_lng?: number | null;
      exclude_field_id?: string | null;
    },
    signal?: AbortSignal,
  ) =>
    // Posted (a polygon is too long for a query string) but abortable, because the
    // map fires this on every edit and only the latest answer matters.
    apiRequest<GeometryValidation>(`${BASE}/fields/validate-geometry`, {
      method: 'POST',
      body,
      signal,
    }),

  mapFields: (
    params: { bbox?: string; zoom?: number; crop?: Crop; limit?: number },
    signal?: AbortSignal,
  ) => api.get<MapFields>(`${BASE}/fields/map`, { ...params }, signal),

  provinces: (country: string, signal?: AbortSignal) =>
    api.get<LocationList>(`${BASE}/locations/provinces`, { country }, signal),

  districts: (province: string, country: string, signal?: AbortSignal) =>
    api.get<LocationList>(`${BASE}/locations/districts`, { province, country }, signal),

  tehsils: (district: string, country: string, signal?: AbortSignal) =>
    api.get<LocationList>(`${BASE}/locations/tehsils`, { district, country }, signal),

  villageSuggestions: (tehsil: string, q: string | undefined, signal?: AbortSignal) =>
    api.get<string[]>(`${BASE}/locations/villages/suggest`, { tehsil, q }, signal),

  postcode: (postcode: string, signal?: AbortSignal) =>
    api.get<PostcodeLocation>(`${BASE}/uk/postcode/${encodeURIComponent(postcode)}`, undefined, signal),
};

/** Query keys for this module, so a mutation can invalidate exactly what it changed. */
export const registerKeys = {
  all: ['register'] as const,
  farmers: (params: FarmerSearchParams) => ['register', 'farmers', params] as const,
  farmer: (id: string) => ['register', 'farmer', id] as const,
  profile: (id: string) => ['register', 'farmer', id, 'profile'] as const,
  fields: (farmerId: string) => ['register', 'farmer', farmerId, 'fields'] as const,
  lookup: (idNumber: string, crop: Crop) => ['register', 'lookup', crop, idNumber] as const,
  map: (bbox: string | undefined, zoom: number | undefined) =>
    ['register', 'map', bbox ?? null, zoom ?? null] as const,
  provinces: (country: string) => ['register', 'provinces', country] as const,
  districts: (province: string | null) => ['register', 'districts', province] as const,
  tehsils: (district: string | null) => ['register', 'tehsils', district] as const,
  villages: (tehsil: string | null, q: string) => ['register', 'villages', tehsil, q] as const,
  postcode: (postcode: string) => ['register', 'postcode', postcode] as const,
};
