/** Delivery list filters and their API parameters. */
import type { Crop } from '../api/types';

export interface DeliveryFilterState {
  crop: Crop | '';
  status: string;
  site_id: string;
  date_from: string;
  date_to: string;
  officer_id: string;
  area: string;
  q: string;
  scope: 'mine' | 'all';
}

export const NO_FILTERS: DeliveryFilterState = {
  crop: '', status: '', site_id: '', date_from: '', date_to: '', officer_id: '', area: '', q: '', scope: 'mine',
};

export function toParams(f: DeliveryFilterState) {
  return {
    crop: f.crop || undefined, status: f.status || undefined, site_id: f.site_id || undefined,
    date_from: f.date_from || undefined, date_to: f.date_to || undefined, officer_id: f.officer_id || undefined,
    district: f.crop === 'cotton' ? f.area || undefined : undefined,
    county: f.crop === 'hemp' ? f.area || undefined : undefined,
    q: f.q.trim() || undefined, scope: f.scope,
  };
}

/** Filters a link may carry in the address. Anything missing or unknown is left empty. */
export function filtersFromUrl(params: URLSearchParams): DeliveryFilterState {
  const crop = params.get('crop');
  const iso = (key: string) => (/^\d{4}-\d{2}-\d{2}$/.test(params.get(key) ?? '') ? params.get(key)! : '');
  return {
    ...NO_FILTERS,
    crop: crop === 'cotton' || crop === 'hemp' ? crop : '',
    status: params.get('status') ?? '',
    date_from: iso('date_from'),
    date_to: iso('date_to'),
    scope: params.get('scope') === 'all' ? 'all' : 'mine',
  };
}
