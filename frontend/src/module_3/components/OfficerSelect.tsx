import { Select } from '@/design-system/components';
import type { OfficerOption } from '../api/types';

export interface OfficerSelectProps {
  officers: OfficerOption[];
  value: string | null;
  onChange: (officerId: string) => void;
  loading?: boolean;
}

/** An officer sees only themself; an administrator can act for any officer. */
export function OfficerSelect({ officers, value, onChange, loading }: OfficerSelectProps) {
  return (
    <Select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      disabled={loading || officers.length <= 1}
      placeholder={loading ? 'Loading officers' : 'Choose an officer'}
      options={officers.map((o) => ({
        value: o.id,
        label: o.field_office_name ? `${o.full_name}, ${o.field_office_name}` : o.full_name,
      }))}
    />
  );
}
