/** API answers for the Dashboard tests, shaped exactly as the server sends them. */
import type {
  Activity,
  Alerts,
  Distribution,
  MapCollection,
  Onboarding,
  Overview,
  Pipeline,
  Stage,
  Timeseries,
} from '../api/types';

const at = '2026-10-23T06:00:00Z';
const base = { crop: 'all' as const, season_year: 2026, scope: 'mine' as const, generated_at: at };

export function stage(over: Partial<Stage> = {}): Stage {
  return {
    key: 'farmers',
    title: 'Farmers registered',
    caption: 'People registered in the programme.',
    count: 100,
    detail: null,
    conversion_pct: null,
    progress_pct: 100,
    link: { path: '/register', params: {} },
    ...over,
  };
}

export const pipeline: Pipeline = {
  ...base,
  stages: [
    stage(),
    stage({ key: 'fields', title: 'Fields mapped', count: 80, conversion_pct: 80, progress_pct: 80 }),
    stage({ key: 'fieldbooks', title: 'Fieldbooks', count: 40, conversion_pct: 50, progress_pct: 40, link: { path: '/fieldbook', params: {} } }),
    stage({ key: 'harvest', title: 'Harvest ready or done', count: 20, conversion_pct: 50, progress_pct: 20, link: { path: '/radar', params: { crop: 'cotton', status: 'ready', season: '2026' } } }),
    stage({ key: 'deliveries', title: 'Deliveries delivered', count: 10, conversion_pct: 50, progress_pct: 10, link: { path: '/deliveries', params: { tab: 'deliveries', status: 'delivered' } } }),
    stage({ key: 'bales', title: 'Heaps and bales produced', count: 5, conversion_pct: 50, progress_pct: 5, link: { path: '/heaps', params: { crop: 'cotton' } } }),
    stage({ key: 'scans', title: 'QR codes scanned', count: 2, conversion_pct: 40, progress_pct: 2, link: { path: '/qr', params: { crop: 'cotton' } } }),
  ],
};

export function overview(over: Partial<Overview> = {}): Overview {
  return {
    ...base,
    range: { key: '30d', from: '2026-09-24', to: '2026-10-23', days: 30 },
    officer: { id: 'o1', full_name: 'Ayesha Khan', field_office_name: 'Multan', is_admin: false },
    units: { area: 'acre', mass: 'maund' },
    kpis: {
      farmers: { total: 100, cotton: 70, hemp: 30 },
      fields: { total: 80, area: 790.4, area_unit: 'acre', area_by_crop: { cotton: 790.4 } },
      fieldbooks: { fields: 80, started: 40, submitted: 20, submitted_pct: 25 },
      ready_now: { fields: 12, estimated_kg: 9600, awaiting_pickup: 4 },
      delivered: { deliveries: 10, kg: 8000, maunds: 200, average_moisture_pct: 9.5 },
      bales: { made: 5, weight_kg: 850, heaps: 1 },
      scans: { total: 2, in_range: 2, public: 1, internal: 1, active_codes: 6, last_scan_at: at },
    },
    ...over,
  };
}

export function series(metric: 'registrations' | 'deliveries'): Timeseries {
  const keys = metric === 'registrations' ? ['farmers', 'fields'] : ['delivered_kg', 'average_moisture_pct'];
  return {
    ...base,
    metric,
    interval: 'day',
    from: '2026-10-22',
    to: '2026-10-23',
    truncated: false,
    series: keys.map((key) => ({
      key,
      label: key,
      unit: '',
      total: 3,
      points: [
        { period_start: '2026-10-22', value: 1 },
        { period_start: '2026-10-23', value: 2 },
      ],
    })),
  };
}

export function distribution(over: Partial<Distribution> = {}): Distribution {
  return {
    ...base,
    focus_crop: 'cotton',
    area_unit: 'acre',
    region_label: 'District',
    readiness: [
      { bucket: 'ready', label: 'Ready', fields: 12, area: 118.6, estimated_kg: 9600 },
      { bucket: 'growing', label: 'Growing', fields: 28, area: 276.6, estimated_kg: 0 },
    ],
    fieldbook_funnel: [{ step_key: 'sowing', title: 'Sowing', order: 3, complete: 40, pct: 100 }],
    fieldbooks_started: 40,
    heap_utilisation: [
      {
        heap_id: 'BWP-G1-H01',
        kind: 'heap',
        crop: 'cotton',
        status: 'open',
        input_kg: 8000,
        expected_output_kg: 2720,
        bales_made: 5,
        max_bales: 16,
        link: { path: '/heaps', params: { crop: 'cotton', heap: 'BWP-G1-H01' } },
      },
    ],
    top_regions: [{ region: 'Multan', fields: 40, area: 395.2 }],
    ...over,
  };
}

export function alerts(over: Partial<Alerts> = {}): Alerts {
  return {
    ...base,
    total: 5,
    critical: 2,
    alerts: [
      {
        key: 'ready_without_pickup',
        title: 'Ready with no pickup request',
        description: 'Fields ready for more than 7 days.',
        count: 3,
        severity: 'attention',
        link: { path: '/radar', params: { status: 'ready', pickup: 'not_requested' } },
        samples: [{ label: '1001-01', sublabel: 'farmer aa, ready 9 days ago', link: { path: '/register/farmers/f1', params: {} } }],
      },
      {
        key: 'overdue_fields',
        title: 'Overdue fields',
        description: 'Past the harvest window.',
        count: 2,
        severity: 'critical',
        link: { path: '/radar', params: { status: 'ready', to: '2026-08-18' } },
        samples: [],
      },
      {
        key: 'idle_heaps',
        title: 'Idle heaps and batches',
        description: 'No activity for 14 days.',
        count: 0,
        severity: 'attention',
        link: { path: '/heaps', params: { status: 'open' } },
        samples: [],
      },
    ],
    ...over,
  };
}

export const activity: Activity = {
  module: null,
  items: [
    {
      id: 'a1',
      at,
      module: 2,
      module_name: 'Register Farmer',
      entity: 'farmer',
      entity_id: 'f1',
      action: 'create',
      summary: 'Farmer added',
      officer_id: 'o1',
      officer_name: 'Ayesha Khan',
      link: { path: '/register/farmers/f1', params: {} },
    },
  ],
  modules: [
    { number: 2, name: 'Register Farmer' },
    { number: 5, name: 'Deliveries' },
  ],
  generated_at: at,
};

export const emptyMap: MapCollection = {
  type: 'FeatureCollection',
  features: [],
  total: 0,
  returned: 0,
  truncated: false,
  crop: 'all',
  season_year: 2026,
  scope: 'mine',
  generated_at: at,
};

export function onboarding(isEmpty: boolean, role = 'officer'): Onboarding {
  return {
    is_empty: isEmpty,
    role,
    scope: 'mine',
    crop: 'all',
    season_year: 2026,
    counts: { farmers: isEmpty ? 0 : 100, fields: isEmpty ? 0 : 80, fieldbooks: isEmpty ? 0 : 40 },
    steps: [
      { key: 'register_farmer', title: role === 'admin' ? 'Register the first farmer' : 'Register your first farmer', description: 'd', done: !isEmpty, count: 0, link: { path: '/register', params: {} } },
      { key: 'map_field', title: 'Map a field', description: 'd', done: !isEmpty, count: 0, link: { path: '/register', params: {} } },
      { key: 'open_fieldbook', title: 'Open a fieldbook', description: 'd', done: !isEmpty, count: 0, link: { path: '/fieldbook', params: {} } },
    ],
    generated_at: at,
  };
}
