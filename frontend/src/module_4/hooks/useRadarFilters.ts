import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { Bucket, Crop, PickupState } from '../api/types';
import type { RadarParams } from '../api/client';

export type RadarView = 'table' | 'map' | 'calendar';

/** Everything the radar shows is described by the URL, so a view can be shared or reloaded. */
export interface RadarFilterState {
  crop: Crop;
  season: number;
  q: string;
  district: string;
  tehsil: string;
  village: string;
  county: string;
  region: string;
  office: string;
  officer: string;
  status: Bucket | '';
  pickup: PickupState | '';
  from: string;
  to: string;
  scope: 'mine' | 'all';
  view: RadarView;
  sort: string;
  page: number;
  month: string;
}

/** Filters that narrow the field set (not view, sort, page or month). */
export const FILTER_KEYS = ['q', 'district', 'tehsil', 'village', 'county', 'region', 'office', 'officer', 'status', 'pickup', 'from', 'to'] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];

const VIEWS: RadarView[] = ['table', 'map', 'calendar'];
const thisMonth = () => new Date().toISOString().slice(0, 7);

export function readFilters(params: URLSearchParams): RadarFilterState {
  const get = (k: string) => params.get(k) ?? '';
  const view = get('view') as RadarView;
  const season = Number(get('season'));
  const page = Number(get('page'));
  return {
    crop: get('crop') === 'hemp' ? 'hemp' : 'cotton',
    season: Number.isInteger(season) && season >= 2000 ? season : new Date().getFullYear(),
    q: get('q'),
    district: get('district'),
    tehsil: get('tehsil'),
    village: get('village'),
    county: get('county'),
    region: get('region'),
    office: get('office'),
    officer: get('officer'),
    status: get('status') as Bucket | '',
    pickup: get('pickup') as PickupState | '',
    from: get('from'),
    to: get('to'),
    scope: get('scope') === 'all' ? 'all' : 'mine',
    view: VIEWS.includes(view) ? view : 'table',
    sort: get('sort') || 'expected_ready',
    page: Number.isInteger(page) && page > 0 ? page : 1,
    month: /^\d{4}-\d{2}$/.test(get('month')) ? get('month') : thisMonth(),
  };
}

/** The API's query parameters for a filter state (view, sort, page and month excluded). */
export function toApiParams(f: RadarFilterState): RadarParams {
  return {
    crop: f.crop,
    season_year: f.season,
    q: f.q || undefined,
    district: f.crop === 'cotton' ? f.district || undefined : undefined,
    tehsil: f.crop === 'cotton' ? f.tehsil || undefined : undefined,
    village: f.crop === 'cotton' ? f.village || undefined : undefined,
    county: f.crop === 'hemp' ? f.county || undefined : undefined,
    region: f.crop === 'hemp' ? f.region || undefined : undefined,
    field_office_id: f.office || undefined,
    officer_id: f.officer || undefined,
    status: f.status || undefined,
    pickup: f.pickup || undefined,
    ready_from: f.from || undefined,
    ready_to: f.to || undefined,
    scope: f.scope,
  };
}

export function activeFilterCount(f: RadarFilterState): number {
  return FILTER_KEYS.filter((k) => f[k] !== '').length;
}

/** Changing location filters clears the levels below; any filter change returns to page 1. */
const CHILDREN: Partial<Record<string, string[]>> = {
  district: ['tehsil', 'village'],
  tehsil: ['village'],
  crop: ['district', 'tehsil', 'village', 'county', 'region', 'office', 'officer', 'status', 'from', 'to'],
};

export function useRadarFilters() {
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => readFilters(params), [params]);

  const update = useCallback(
    (changes: Partial<Record<keyof RadarFilterState, string | number>>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(changes)) {
            if (value === '' || value === undefined || value === null) next.delete(key);
            else next.set(key, String(value));
            for (const child of CHILDREN[key] ?? []) if (!(child in changes)) next.delete(child);
          }
          if (!('page' in changes)) next.delete('page');
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const clear = useCallback(() => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const key of FILTER_KEYS) next.delete(key);
        next.delete('page');
        return next;
      },
      { replace: true },
    );
  }, [setParams]);

  return { filters, apiParams: useMemo(() => toApiParams(filters), [filters]), update, clear };
}
