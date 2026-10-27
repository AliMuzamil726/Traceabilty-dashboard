import { Lock } from 'lucide-react';
import { Badge } from '@/design-system/components/Badge';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { KeyValueList } from '@/design-system/components/KeyValueList';
import { countryName } from '@/core/utils/format';
import type { Farmer, SeasonProfile } from '../api/types';
import { CROP_LABEL } from '../format';

export interface FarmerSummaryCardProps {
  farmer: Farmer;
  season?: SeasonProfile | null;
  /** Shown on the field page, where farmer details are deliberately not editable. */
  readOnlyNotice?: boolean;
}

/**
 * The farmer, as read-only context.
 *
 * Used on the field mapping page, where farmer details must not be editable: mapping a
 * boundary and correcting a name are different jobs with different audit trails, so the
 * card says so rather than tempting the officer with inputs that would not save.
 *
 * The ID number arrives already masked unless this officer is allowed to see it, so
 * there is nothing to decide here: whatever the API sent is what is shown.
 */
export function FarmerSummaryCard({ farmer, season, readOnlyNotice }: FarmerSummaryCardProps) {
  const isCotton = farmer.crop === 'cotton';

  const identity = [
    { label: 'SAWIE ID', value: farmer.sawie_id, mono: true },
    { label: 'Name', value: farmer.name },
    isCotton
      ? { label: 'Father name', value: farmer.father_name ?? '-' }
      : { label: 'Farm name', value: farmer.farm_name ?? '-' },
    { label: 'ID number', value: farmer.id_number, mono: true },
    { label: 'Phone', value: farmer.phone ?? '-', mono: true },
  ];

  const place = isCotton
    ? [
        { label: 'Province', value: farmer.province ?? '-' },
        { label: 'District', value: farmer.district ?? '-' },
        { label: 'Tehsil or city', value: farmer.tehsil ?? '-' },
        { label: 'Village or town', value: farmer.village ?? '-' },
      ]
    : [
        { label: 'Postcode', value: farmer.postcode ?? '-', mono: true },
        { label: 'County', value: farmer.county ?? '-' },
        { label: 'Region', value: farmer.region ?? '-' },
        { label: 'Licence number', value: farmer.home_office_licence_no ?? '-', mono: true },
      ];

  const crop = [
    { label: 'Crop', value: CROP_LABEL[farmer.crop] },
    { label: 'Country', value: countryName(farmer.country) },
    { label: 'Variety', value: season?.variety ?? 'Not recorded this season' },
    { label: 'Tenure', value: season?.tenure ?? 'Not recorded this season' },
    { label: 'Previous crop', value: season?.previous_crop ?? '-' },
    { label: 'Field office', value: farmer.field_office?.name ?? '-' },
  ];

  return (
    <Card padding="lg">
      <SectionHeader
        title="Farmer"
        description={readOnlyNotice ? 'Change these details from the farmer record' : undefined}
        actions={
          readOnlyNotice ? (
            <Badge tone="neutral">
              <Lock className="h-3 w-3" aria-hidden />
              Read only here
            </Badge>
          ) : undefined
        }
      />
      <div className="mt-4 grid gap-x-8 gap-y-2 lg:grid-cols-3">
        <KeyValueList items={identity} />
        <KeyValueList items={place} />
        <KeyValueList items={crop} />
      </div>
      {!farmer.sensitive_visible && (
        <p className="mt-4 text-sm text-muted">
          The ID number and phone are masked because another officer registered this farmer.
        </p>
      )}
    </Card>
  );
}
