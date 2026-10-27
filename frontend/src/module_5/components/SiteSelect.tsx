import { useSites } from '@/core/hooks/useSharedData';
import { Select } from '@/design-system/components';
import type { Crop } from '../api/types';
import { siteWord } from '../lib/variance';

export interface SiteSelectProps {
  crop: Crop | undefined;
  value: string;
  onChange: (siteId: string) => void;
  invalid?: boolean;
  placeholder?: string;
  id?: string;
}

/** Ginners for cotton, processors for hemp. */
export function SiteSelect({ crop, value, onChange, invalid, placeholder, id }: SiteSelectProps) {
  const sites = useSites(crop);
  const word = crop ? siteWord(crop).site.toLowerCase() : 'site';
  return (
    <Select
      id={id}
      value={value}
      invalid={invalid}
      placeholder={sites.isLoading ? 'Loading' : (placeholder ?? `Choose a ${word}`)}
      options={(sites.data ?? []).map((s) => ({ value: s.id, label: `${s.name} (${s.code})` }))}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
