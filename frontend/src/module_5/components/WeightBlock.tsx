import { cn } from '@/core/utils/cn';
import { KeyValueList } from '@/design-system/components';
import type { DeliveryDetail } from '../api/types';
import { LEVEL_CLASSES, LEVEL_LABEL } from '../lib/status';
import { kgText } from '../lib/variance';

/** Estimated, field and weighbridge weights with the variance and moisture. */
export function WeightBlock({ d }: { d: DeliveryDetail }) {
  const moistureHigh = d.moisture_pct !== null && d.moisture_pct > d.thresholds.moisture_warn_pct;
  return (
    <KeyValueList
      columns={2}
      items={[
        { label: 'Estimated', value: kgText(d.estimated_quantity_kg, d.crop) },
        { label: 'Field weight', value: kgText(d.field_weight_kg, d.crop) },
        { label: 'Weighbridge', value: kgText(d.weighbridge_weight_kg, d.crop) },
        {
          label: 'Moisture',
          value:
            d.moisture_pct === null ? '-' : (
              <span className={moistureHigh ? 'text-wheat-600' : undefined}>
                {d.moisture_pct}%{moistureHigh ? `, above the ${d.thresholds.moisture_warn_pct}% limit` : ''}
              </span>
            ),
        },
        {
          label: 'Variance',
          value:
            d.variance_level === null ? '-' : (
              <span className={cn('font-medium', LEVEL_CLASSES[d.variance_level])}>
                {d.variance_kg !== null && d.variance_kg > 0 ? '+' : ''}
                {d.variance_kg} kg ({d.variance_pct}%), {LEVEL_LABEL[d.variance_level]}
              </span>
            ),
        },
      ]}
    />
  );
}
