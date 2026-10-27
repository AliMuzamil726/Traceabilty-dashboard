import { useCallback, useRef } from 'react';
import { Badge, Combobox, type SelectOption } from '@/design-system/components';
import { fieldbookApi } from '../api/client';
import type { FarmerOption } from '../api/types';
import { farmerLabel } from '../lib/display';

export interface FarmerComboboxProps {
  officerId: string | null;
  seasonYear: number;
  value: string | null;
  selectedLabel?: string;
  onChange: (farmer: FarmerOption | null) => void;
}

const STATUS: Record<string, { label: string; tone: 'neutral' | 'warning' | 'success' | 'info' }> = {
  no_field: { label: 'No field', tone: 'neutral' },
  not_started: { label: 'Not started', tone: 'neutral' },
  in_progress: { label: 'In progress', tone: 'warning' },
  submitted: { label: 'Submitted', tone: 'success' },
};

/** Search the officer's own farmers by SAWIE ID or name. */
export function FarmerCombobox({ officerId, seasonYear, value, selectedLabel, onChange }: FarmerComboboxProps) {
  const found = useRef(new Map<string, FarmerOption>());

  const load = useCallback(
    async (q: string, signal: AbortSignal): Promise<SelectOption[]> => {
      if (!officerId) return [];
      const rows = await fieldbookApi.farmers(officerId, q.trim() || undefined, seasonYear, signal);
      for (const row of rows) found.current.set(row.id, row);
      return rows.map((r) => ({ value: r.id, label: farmerLabel(r) }));
    },
    [officerId, seasonYear],
  );

  return (
    <Combobox
      value={value}
      selectedLabel={selectedLabel}
      loadOptions={load}
      disabled={!officerId}
      placeholder="Search by SAWIE ID or name"
      emptyText="No farmers found for this officer"
      onChange={(id) => onChange(id ? (found.current.get(id) ?? null) : null)}
      renderMeta={(option) => {
        const farmer = found.current.get(option.value);
        if (!farmer) return null;
        const status = STATUS[farmer.fieldbook_status] ?? STATUS.not_started!;
        return (
          <>
            <Badge size="sm" tone="accent">
              {farmer.crop === 'cotton' ? 'Cotton' : 'Hemp'}
            </Badge>
            <Badge size="sm" tone={status.tone}>
              {status.label}
            </Badge>
          </>
        );
      }}
    />
  );
}
