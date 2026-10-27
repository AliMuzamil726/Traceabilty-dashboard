import { useQuery } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { useState } from 'react';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { Select } from '@/design-system/components/Select';
import { settingsApi, settingsKeys } from '../api/client';
import { AuditTable } from '../components/AuditTable';
import { useAuditLog } from '../hooks/useSettings';

const MODULE_NAMES: Record<number, string> = {
  1: 'Home',
  2: 'Register Farmer',
  3: 'Fieldbook',
  4: 'Harvest Radar',
  5: 'Deliveries',
  6: 'Heap',
  7: 'QR Tracing',
  8: 'Settings',
};

/** Every change anyone made, searchable and exportable, and never editable. */
export default function AuditPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);

  const facets = useQuery({
    queryKey: settingsKeys.auditFacets,
    queryFn: ({ signal }) => settingsApi.auditFacets(signal),
  });

  const query = { ...filters, page, page_size: 50 };
  const log = useAuditLog(query);

  const set = (key: string, value: string) => {
    setPage(1);
    setFilters((current) => {
      const next = { ...current };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="Audit log"
        description="Who changed what, and what it was before. Entries can never be edited or removed."
        actions={
          <a
            href={settingsApi.auditCsvUrl(filters)}
            className="inline-flex items-center gap-1.5 rounded-control px-2.5 py-1.5 text-sm text-ink hover:bg-canvas"
          >
            <Download className="h-4 w-4" aria-hidden />
            Export CSV
          </a>
        }
      />

      <Card padding="sm">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <FormField label="Module">
            <Select
              value={filters.module ?? ''}
              onChange={(event) => set('module', event.target.value)}
              placeholder="Every module"
              options={(facets.data?.modules ?? []).map((number) => ({
                value: String(number),
                label: MODULE_NAMES[number] ?? `Module ${number}`,
              }))}
            />
          </FormField>
          <FormField label="Record type">
            <Select
              value={filters.entity ?? ''}
              onChange={(event) => set('entity', event.target.value)}
              placeholder="Every type"
              options={(facets.data?.entities ?? []).map((entity) => ({
                value: entity,
                label: entity.replace(/_/g, ' '),
              }))}
            />
          </FormField>
          <FormField label="Officer">
            <Select
              value={filters.officer_id ?? ''}
              onChange={(event) => set('officer_id', event.target.value)}
              placeholder="Everyone"
              options={(facets.data?.officers ?? []).map((officer) => ({
                value: officer.id,
                label: officer.name,
              }))}
            />
          </FormField>
          <FormField label="From">
            <Input
              type="date"
              value={filters.date_from ?? ''}
              onChange={(event) => set('date_from', event.target.value)}
            />
          </FormField>
          <FormField label="To">
            <Input
              type="date"
              value={filters.date_to ?? ''}
              onChange={(event) => set('date_to', event.target.value)}
            />
          </FormField>
        </div>
      </Card>

      <AuditTable page={log.data} loading={log.isLoading} onPageChange={setPage} />
    </div>
  );
}
