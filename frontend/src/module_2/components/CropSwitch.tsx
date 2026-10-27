import { useState } from 'react';
import { Badge } from '@/design-system/components/Badge';
import { ConfirmDialog } from '@/design-system/components/ConfirmDialog';
import { SegmentedControl } from '@/design-system/components/SegmentedControl';
import { countryName } from '@/core/utils/format';
import type { Crop } from '../api/types';
import { CROP_COUNTRY } from '../format';

export interface CropSwitchProps {
  value: Crop;
  onChange: (crop: Crop) => void;
  /** True when the officer has already typed something worth protecting. */
  dirty: boolean;
  disabled?: boolean;
}

const OPTIONS = [
  { value: 'cotton' as const, label: 'Cotton' },
  { value: 'hemp' as const, label: 'Hemp' },
];

/**
 * The first control on the form. The crop decides the country, which fields appear and
 * which dropdown lists load, so the country is shown beside it as a read-only chip:
 * the officer can see the consequence of the choice rather than having to know it.
 *
 * Switching crop after typing clears the crop-specific fields, so it asks first.
 */
export function CropSwitch({ value, onChange, dirty, disabled }: CropSwitchProps) {
  const [pending, setPending] = useState<Crop | null>(null);

  const request = (next: Crop) => {
    if (next === value) return;
    if (dirty) setPending(next);
    else onChange(next);
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <SegmentedControl
        aria-label="Crop programme"
        value={value}
        onChange={request}
        options={OPTIONS.map((o) => ({ ...o, disabled }))}
      />
      <Badge tone="info">{countryName(CROP_COUNTRY[value])}</Badge>

      <ConfirmDialog
        open={pending !== null}
        title="Change crop programme?"
        description="The fields that belong to this programme will be cleared, because the other programme asks for different details."
        confirmLabel="Change programme"
        cancelLabel="Keep editing"
        onConfirm={() => {
          if (pending) onChange(pending);
          setPending(null);
        }}
        onCancel={() => setPending(null)}
      />
    </div>
  );
}
