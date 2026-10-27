import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { CropFilter, RangeKey, Scope } from '../api/types';
import type { DashboardParams } from '../api/client';

/**
 * The header's controls live in the web address, so a view can be shared, reloaded or
 * sent to a colleague. Nothing about the dashboard is held in component state.
 */
export interface DashboardFilterState {
  crop: CropFilter;
  season: number;
  range: RangeKey;
  from: string;
  to: string;
  /** Empty until the officer chooses: the server then picks by role. */
  scope: Scope | '';
  /** Which module's entries the activity feed shows. */
  module: number | null;
}

const RANGES: RangeKey[] = ['7d', '30d', 'season', 'custom'];
export const RANGE_LABELS: Record<RangeKey, string> = {
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  season: 'This season',
  custom: 'Custom',
};

export function readFilters(params: URLSearchParams): DashboardFilterState {
  const get = (key: string) => params.get(key) ?? '';
  const crop = get('crop');
  const range = get('range') as RangeKey;
  const season = Number(get('season'));
  const module = Number(get('module'));
  return {
    crop: crop === 'cotton' || crop === 'hemp' ? crop : 'all',
    season: Number.isInteger(season) && season >= 2000 ? season : new Date().getFullYear(),
    range: RANGES.includes(range) ? range : '30d',
    from: get('from'),
    to: get('to'),
    scope: get('scope') === 'mine' || get('scope') === 'all' ? (get('scope') as Scope) : '',
    module: Number.isInteger(module) && module >= 1 && module <= 8 ? module : null,
  };
}

/** The API's query parameters for a filter state. A custom range needs both ends. */
export function toApiParams(f: DashboardFilterState): DashboardParams {
  const custom = f.range === 'custom' && f.from !== '' && f.to !== '';
  return {
    crop: f.crop,
    season_year: f.season,
    range: custom || f.range !== 'custom' ? f.range : '30d',
    from: custom ? f.from : undefined,
    to: custom ? f.to : undefined,
    scope: f.scope || undefined,
  };
}

/** A custom range the officer has only half filled in should not be sent yet. */
export function isRangeIncomplete(f: DashboardFilterState): boolean {
  return f.range === 'custom' && (f.from === '' || f.to === '');
}

type Change = Partial<Record<keyof DashboardFilterState, string | number | null>>;

/** Leaving the custom range clears its dates, so the address stays honest. */
const CLEARS: Partial<Record<string, string[]>> = { range: ['from', 'to'] };

export function useDashboardFilters() {
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => readFilters(params), [params]);

  const update = useCallback(
    (changes: Change) => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          for (const [key, value] of Object.entries(changes)) {
            if (value === '' || value === null || value === undefined) next.delete(key);
            else next.set(key, String(value));
            if (key === 'range' && value === 'custom') continue;
            for (const child of CLEARS[key] ?? []) if (!(child in changes)) next.delete(child);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  return {
    filters,
    apiParams: useMemo(() => toApiParams(filters), [filters]),
    rangeIncomplete: isRangeIncomplete(filters),
    update,
  };
}
