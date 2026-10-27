import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { FormField } from '@/design-system/components/FormField';
import { NumberInput } from '@/design-system/components/NumberInput';
import { Skeleton } from '@/design-system/components/Skeleton';
import { settingsApi } from '../api/client';
import type { ClockPreview, CropConfig } from '../api/types';
import { ImpactPreview } from '../components/ImpactPreview';
import { ChangedMarker, StickySaveBar } from '../components/StickySaveBar';
import { useConfigBlock, useSaveConfigBlock } from '../hooks/useSettings';
import { GroupPage } from './GroupPage';

const FIELDS: { key: string; label: string; hint: string }[] = [
  { key: 'approach_day', label: 'Approaching from day', hint: 'Days after sowing when the radar starts watching a field.' },
  { key: 'ready_day', label: 'Ready from day', hint: 'When the field is treated as ready to pick.' },
  { key: 'window_end_day', label: 'Window ends on day', hint: 'After this the field counts as overdue.' },
];

const CROP_LABEL: Record<string, string> = { cotton: 'Cotton', hemp: 'Hemp' };

/** The crop clock, with the number of fields a change would move. */
export default function CropsSeasonPage() {
  const config = useConfigBlock<CropConfig>('clock');
  const save = useSaveConfigBlock('clock');
  const [draft, setDraft] = useState<Record<string, Record<string, number>>>({});

  useEffect(() => {
    if (config.data) setDraft(structuredClone(config.data.crops));
  }, [config.dataUpdatedAt]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = useMemo(
    () => config.data !== undefined && JSON.stringify(draft) !== JSON.stringify(config.data.crops),
    [draft, config.data],
  );

  const preview = useQuery<ClockPreview>({
    queryKey: ['settings', 'clock-preview', draft],
    queryFn: () => settingsApi.previewClock(draft),
    enabled: dirty && Object.keys(draft).length > 0,
  });

  const invalid = Object.entries(draft).find(([, values]) => {
    const approach = values.approach_day ?? 0;
    const ready = values.ready_day ?? 0;
    const end = values.window_end_day ?? 0;
    return !(approach < ready && ready < end);
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <SectionHeader
          title="Crop clock"
          description="How many days after sowing a field is approaching, ready, and past its window."
        />

        {config.isLoading ? (
          <Skeleton className="h-48 w-full" shape="block" />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {Object.entries(draft).map(([crop, values]) => (
              <Card key={crop} padding="md">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-medium text-ink">{CROP_LABEL[crop] ?? crop}</h3>
                  <ChangedMarker
                    changed={
                      JSON.stringify(values) !== JSON.stringify(config.data?.crops[crop] ?? {})
                    }
                  />
                </div>
                <div className="mt-3 flex flex-col gap-3">
                  {FIELDS.map((field) => (
                    <FormField key={field.key} label={field.label} hint={field.hint}>
                      <NumberInput
                        value={values[field.key] ?? null}
                        unit="days"
                        onValueChange={(next) =>
                          setDraft((current) => ({
                            ...current,
                            [crop]: { ...current[crop], [field.key]: next ?? 0 },
                          }))
                        }
                      />
                    </FormField>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        )}

        {invalid && (
          <p className="rounded-control bg-danger-tint px-3 py-2 text-sm text-danger">
            For {CROP_LABEL[invalid[0]] ?? invalid[0]}, the approach day must come before the ready
            day, and the ready day before the window end.
          </p>
        )}

        {dirty && !invalid && (
          <ImpactPreview preview={preview.data} loading={preview.isLoading} />
        )}

        <StickySaveBar
          dirty={dirty}
          saving={save.isPending}
          message={
            invalid
              ? 'Fix the days before saving.'
              : preview.data
                ? `${preview.data.fields_moving} field(s) would change bucket.`
                : 'The crop clock has changed.'
          }
          onSave={() =>
            !invalid && save.mutate({ values: draft, version: config.data?.version })
          }
          onDiscard={() => config.data && setDraft(structuredClone(config.data.crops))}
        />
      </div>

      <GroupPage
        group="programme"
        title="Season"
        description="The season new work opens in, and how a season is written on screen."
      />
    </div>
  );
}
