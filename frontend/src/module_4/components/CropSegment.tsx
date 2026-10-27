import { SegmentedControl } from '@/design-system/components';
import type { Crop } from '../api/types';

/** Cotton (Pakistan, acres) or hemp (United Kingdom, hectares): changes filters, units and wording. */
export function CropSegment({ value, onChange }: { value: Crop; onChange: (crop: Crop) => void }) {
  return (
    <SegmentedControl
      aria-label="Crop"
      value={value}
      onChange={onChange}
      options={[
        { value: 'cotton', label: 'Cotton' },
        { value: 'hemp', label: 'Hemp' },
      ]}
    />
  );
}
