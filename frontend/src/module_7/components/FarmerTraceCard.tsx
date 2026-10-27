import { Lock } from 'lucide-react';
import { formatDate, formatNumber } from '@/core/utils/format';
import { Card, KeyValueList, ProgressBar } from '@/design-system/components';
import type { Crop, TraceFarmer } from '../api/types';

/** One contributing farmer. ID numbers stay masked unless this officer registered them or is an administrator. */
export function FarmerTraceCard({ farmer, crop }: { farmer: TraceFarmer; crop: Crop }) {
  return (
    <Card as="article" padding="md" aria-label={farmer.name} className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{farmer.name}</p>
          <p className="text-xs text-muted">SAWIE ID <span className="mono-id">{farmer.sawie_id ?? '-'}</span></p>
        </div>
        <div className="text-right">
          <p className="text-lg font-semibold tabular-nums text-forest-700">{farmer.pct ?? 0}%</p>
          <p className="text-xs text-muted">{formatNumber(farmer.kg ?? 0)} kg</p>
        </div>
      </div>
      <ProgressBar value={farmer.pct ?? 0} max={100} label={`Share of ${farmer.name}`} />
      <KeyValueList items={[
        { label: crop === 'cotton' ? 'Father name' : 'Farm', value: farmer.father_or_farm ?? '-' },
        {
          label: crop === 'cotton' ? 'CNIC' : 'ID number',
          mono: true,
          value: (
            <span className="inline-flex items-center gap-1.5">
              {farmer.id_number ?? '-'}
              {!farmer.sensitive_visible && <Lock aria-label="Masked" className="h-3.5 w-3.5 text-muted" />}
            </span>
          ),
        },
        ...(farmer.sensitive_visible && farmer.phone ? [{ label: 'Phone', value: farmer.phone, mono: true }] : []),
        ...(crop === 'hemp' && farmer.licence_no ? [{ label: 'Licence', value: farmer.licence_no, mono: true }] : []),
        { label: 'Location', value: farmer.location ?? '-' },
        { label: 'Registered', value: `${farmer.registered_at ? formatDate(farmer.registered_at) : '-'}${farmer.registered_by ? ` by ${farmer.registered_by}` : ''}` },
      ]} />
    </Card>
  );
}
