import { Search, X } from 'lucide-react';
import { useOfficers } from '@/core/hooks/useSharedData';
import { Button, DatePicker, FormField, Input, Select } from '@/design-system/components';
import type { Crop } from '../api/types';
import { NO_FILTERS, type DeliveryFilterState } from '../lib/filters';
import { STATUS_LABEL } from '../lib/status';
import { SiteSelect } from './SiteSelect';

export function DeliveryFilters({ value: f, onChange, isAdmin }: { value: DeliveryFilterState; onChange: (f: DeliveryFilterState) => void; isAdmin: boolean }) {
  const officers = useOfficers();
  const set = <K extends keyof DeliveryFilterState>(key: K, v: DeliveryFilterState[K]) =>
    onChange({ ...f, [key]: v, ...(key === 'crop' ? { site_id: '', area: '' } : {}) });
  const active = (Object.keys(NO_FILTERS) as (keyof DeliveryFilterState)[]).some((k) => k !== 'scope' && f[k] !== NO_FILTERS[k]);
  return (
    <section aria-label="In transit filters" className="flex flex-col gap-3 rounded-card border border-line bg-surface p-3">
      <Input
        aria-label="Search by delivery number, farmer, SAWIE ID or vehicle"
        placeholder="Search delivery, farmer, SAWIE ID or vehicle"
        leadingIcon={<Search className="h-4 w-4" />}
        value={f.q}
        onChange={(e) => set('q', e.target.value)}
      />
      <div className="grid grid-cols-2 gap-2">
        <FormField label="Crop">
          <Select value={f.crop} placeholder="Both crops" options={[{ value: 'cotton', label: 'Cotton' }, { value: 'hemp', label: 'Hemp' }]} onChange={(e) => set('crop', e.target.value as Crop | '')} />
        </FormField>
        <FormField label="Status">
          <Select value={f.status} placeholder="Any status" options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))} onChange={(e) => set('status', e.target.value)} />
        </FormField>
        <FormField label={f.crop === 'hemp' ? 'Processor' : f.crop === 'cotton' ? 'Ginner' : 'Site'} className="col-span-2">
          <SiteSelect crop={f.crop || undefined} value={f.site_id} onChange={(v) => set('site_id', v)} placeholder="Any site" />
        </FormField>
        <FormField label="From">
          <DatePicker value={f.date_from || null} onValueChange={(v) => set('date_from', v ?? '')} />
        </FormField>
        <FormField label="To">
          <DatePicker value={f.date_to || null} onValueChange={(v) => set('date_to', v ?? '')} />
        </FormField>
        {f.crop && (
          <FormField label={f.crop === 'cotton' ? 'District' : 'County'}>
            <Input value={f.area} onChange={(e) => set('area', e.target.value)} />
          </FormField>
        )}
        <FormField label="Officer">
          <Select value={f.officer_id} placeholder="Any officer" options={(officers.data?.items ?? []).filter((o) => o.role === 'officer').map((o) => ({ value: o.id, label: o.full_name }))} onChange={(e) => set('officer_id', e.target.value)} />
        </FormField>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {!isAdmin ? (
          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" role="switch" aria-checked={f.scope === 'all'} className="h-4 w-4 accent-forest-700" checked={f.scope === 'all'} onChange={(e) => set('scope', e.target.checked ? 'all' : 'mine')} />
            All farmers <span className="text-muted">(others read only)</span>
          </label>
        ) : <span />}
        {active && (
          <Button size="sm" variant="ghost" leftIcon={<X className="h-4 w-4" />} onClick={() => onChange({ ...NO_FILTERS, scope: f.scope })}>
            Clear filters
          </Button>
        )}
      </div>
    </section>
  );
}
