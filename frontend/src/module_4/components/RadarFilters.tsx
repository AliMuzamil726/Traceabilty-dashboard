import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, Search, SlidersHorizontal, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { cn } from '@/core/utils/cn';
import { Badge, Button, DatePicker, FormField, Input, Select } from '@/design-system/components';
import { transition } from '@/design-system/motion';
import type { Facets } from '../api/types';
import { activeFilterCount, type RadarFilterState } from '../hooks/useRadarFilters';
import { BUCKET_LABEL, BUCKET_ORDER, PICKUP_LABEL } from '../lib/status';

export interface RadarFiltersProps {
  filters: RadarFilterState;
  facets: Facets | undefined;
  isAdmin: boolean;
  onChange: (changes: Partial<Record<keyof RadarFilterState, string>>) => void;
  onClear: () => void;
}

const opts = (values: string[] | undefined) => (values ?? []).map((v) => ({ value: v, label: v }));

/**
 * Filters for every view. Location options come from the fields actually on the radar,
 * cascading district, tehsil, village (cotton) or county and region (hemp). Status and
 * pickup state are the API's own states, not reference lists.
 */
export function RadarFilters({ filters: f, facets, isAdmin, onChange, onClear }: RadarFiltersProps) {
  const [open, setOpen] = useState(() => activeFilterCount(f) > 0);
  const [search, setSearch] = useState(f.q);
  const count = activeFilterCount(f);

  // Type freely; the URL (and the query) follow a moment later.
  useEffect(() => setSearch(f.q), [f.q]);
  useEffect(() => {
    if (search === f.q) return undefined;
    const t = window.setTimeout(() => onChange({ q: search.trim() }), 300);
    return () => window.clearTimeout(t);
  }, [search, f.q, onChange]);

  return (
    <section aria-label="Filters" className="rounded-card border border-line bg-surface">
      <div className="flex flex-wrap items-center gap-3 p-3">
        <div className="min-w-[220px] flex-1">
          <Input
            aria-label="Search by SAWIE ID, field ID or farmer name"
            placeholder="Search SAWIE ID, field ID or farmer"
            leadingIcon={<Search className="h-4 w-4" />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {!isAdmin && (
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              role="switch"
              aria-checked={f.scope === 'all'}
              className="h-4 w-4 accent-forest-700"
              checked={f.scope === 'all'}
              onChange={(e) => onChange({ scope: e.target.checked ? 'all' : '' })}
            />
            All farmers
            <span className="text-muted">(others read only)</span>
          </label>
        )}
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<SlidersHorizontal className="h-4 w-4" />}
          rightIcon={<ChevronDown className={cn('h-4 w-4 transition-transform', open && 'rotate-180')} />}
          aria-expanded={open}
          aria-controls="radar-filter-panel"
          onClick={() => setOpen(!open)}
        >
          Filters
        </Button>
        {count > 0 && (
          <>
            <Badge tone="accent" size="sm">
              {count} {count === 1 ? 'filter' : 'filters'}
            </Badge>
            <Button variant="ghost" size="sm" leftIcon={<X className="h-4 w-4" />} onClick={onClear}>
              Clear filters
            </Button>
          </>
        )}
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id="radar-filter-panel"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={transition('base')}
            className="overflow-hidden"
          >
            <div className="grid grid-cols-1 gap-3 border-t border-line p-3 sm:grid-cols-2 lg:grid-cols-4">
              {f.crop === 'cotton' ? (
                <>
                  <FormField label="District">
                    <Select value={f.district} placeholder="All districts" options={opts(facets?.districts)} onChange={(e) => onChange({ district: e.target.value })} />
                  </FormField>
                  <FormField label="Tehsil">
                    <Select
                      value={f.tehsil}
                      placeholder={f.district ? 'All tehsils' : 'Choose a district first'}
                      disabled={!f.district}
                      options={opts(facets?.tehsils[f.district])}
                      onChange={(e) => onChange({ tehsil: e.target.value })}
                    />
                  </FormField>
                  <FormField label="Village">
                    <Select
                      value={f.village}
                      placeholder={f.tehsil ? 'All villages' : 'Choose a tehsil first'}
                      disabled={!f.tehsil}
                      options={opts(facets?.villages[f.tehsil])}
                      onChange={(e) => onChange({ village: e.target.value })}
                    />
                  </FormField>
                </>
              ) : (
                <>
                  <FormField label="County">
                    <Select value={f.county} placeholder="All counties" options={opts(facets?.counties)} onChange={(e) => onChange({ county: e.target.value })} />
                  </FormField>
                  <FormField label="Region">
                    <Select value={f.region} placeholder="All regions" options={opts(facets?.regions)} onChange={(e) => onChange({ region: e.target.value })} />
                  </FormField>
                </>
              )}
              <FormField label="Field office">
                <Select value={f.office} placeholder="All offices" options={facets?.offices ?? []} onChange={(e) => onChange({ office: e.target.value })} />
              </FormField>
              <FormField label="Field officer">
                <Select value={f.officer} placeholder="All officers" options={facets?.officers ?? []} onChange={(e) => onChange({ officer: e.target.value })} />
              </FormField>
              <FormField label="Status">
                <Select
                  value={f.status}
                  placeholder="All statuses"
                  options={BUCKET_ORDER.map((b) => ({ value: b, label: BUCKET_LABEL[b] }))}
                  onChange={(e) => onChange({ status: e.target.value })}
                />
              </FormField>
              <FormField label="Pickup state">
                <Select
                  value={f.pickup}
                  placeholder="Any pickup state"
                  options={Object.entries(PICKUP_LABEL).map(([value, label]) => ({ value, label }))}
                  onChange={(e) => onChange({ pickup: e.target.value })}
                />
              </FormField>
              <FormField label="Expected ready from">
                <DatePicker value={f.from || null} max={f.to || undefined} onValueChange={(v) => onChange({ from: v ?? '' })} />
              </FormField>
              <FormField label="Expected ready to">
                <DatePicker value={f.to || null} min={f.from || undefined} onValueChange={(v) => onChange({ to: v ?? '' })} />
              </FormField>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
