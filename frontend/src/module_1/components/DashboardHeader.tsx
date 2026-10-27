import { Download } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/design-system/components/Button';
import { DatePicker } from '@/design-system/components/DatePicker';
import { Select } from '@/design-system/components/Select';
import { SegmentedControl } from '@/design-system/components/SegmentedControl';
import type { CropFilter, RangeKey } from '../api/types';
import { RANGE_LABELS, type DashboardFilterState } from '../hooks/useDashboardFilters';
import { ExportDataDialog } from './ExportDataDialog';

export interface DashboardHeaderProps {
  filters: DashboardFilterState;
  onChange: (changes: Partial<Record<keyof DashboardFilterState, string | number | null>>) => void;
  rangeIncomplete: boolean;
}

const CROPS: { value: CropFilter; label: string }[] = [
  { value: 'all', label: 'All crops' },
  { value: 'cotton', label: 'Cotton' },
  { value: 'hemp', label: 'Hemp' },
];

const RANGES: RangeKey[] = ['7d', '30d', 'season', 'custom'];

/** Four seasons back is as far as the data goes, and as far as anyone looks. */
function seasonOptions(current: number): { value: string; label: string }[] {
  const thisYear = new Date().getFullYear();
  const years = new Set([current, thisYear, thisYear - 1, thisYear - 2, thisYear - 3]);
  return [...years].sort((a, b) => b - a).map((y) => ({ value: String(y), label: String(y) }));
}

/** The page title ("Home"), with crop/date controls and the top Export Data button. */
export function DashboardHeader({ filters, onChange, rangeIncomplete }: DashboardHeaderProps) {
  const [exportOpen, setExportOpen] = useState(false);

  return (
    <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
      <h1 className="text-xl font-semibold tracking-[-0.01em] text-ink">Home</h1>

      <div className="flex flex-wrap items-center gap-2" aria-label="Home filters" role="group">
        <SegmentedControl
          aria-label="Crop programme"
          value={filters.crop}
          onChange={(crop) => onChange({ crop })}
          options={CROPS}
          size="sm"
        />
        <Select
          aria-label="Season year"
          value={String(filters.season)}
          options={seasonOptions(filters.season)}
          onChange={(e) => onChange({ season: e.target.value })}
          className="h-8 w-[76px] text-xs"
        />
        <Select
          aria-label="Date range"
          value={filters.range}
          options={RANGES.map((r) => ({ value: r, label: RANGE_LABELS[r] }))}
          onChange={(e) => onChange({ range: e.target.value })}
          className="h-9 w-[146px]"
        />
        {filters.range === 'custom' && (
          <>
            <DatePicker
              aria-label="Range starts"
              value={filters.from || null}
              onValueChange={(value) => onChange({ from: value ?? '' })}
              max={filters.to || undefined}
              className="h-9"
            />
            <DatePicker
              aria-label="Range ends"
              value={filters.to || null}
              onValueChange={(value) => onChange({ to: value ?? '' })}
              min={filters.from || undefined}
              className="h-9"
            />
          </>
        )}
        <Button
          type="button"
          variant="primary"
          size="sm"
          leftIcon={<Download className="h-4 w-4" />}
          onClick={() => setExportOpen(true)}
        >
          Export Data
        </Button>
      </div>

      {rangeIncomplete && (
        <p className="w-full text-sm text-muted" role="status">
          Pick both dates.
        </p>
      )}

      <ExportDataDialog
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        seasonYear={filters.season}
        cropFilter={filters.crop}
      />
    </header>
  );
}
