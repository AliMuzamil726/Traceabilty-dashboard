import { useEffect, useMemo, useState } from 'react';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { FormField } from '@/design-system/components/FormField';
import { KeyValueList } from '@/design-system/components/KeyValueList';
import { NumberInput } from '@/design-system/components/NumberInput';
import { Skeleton } from '@/design-system/components/Skeleton';
import type { CropConfig } from '../api/types';
import { ChangedMarker, StickySaveBar } from '../components/StickySaveBar';
import { useConfigBlock, useSaveConfigBlock } from '../hooks/useSettings';

const CROP_LABEL: Record<string, string> = { cotton: 'Cotton', hemp: 'Hemp' };

const LABELS: Record<string, { label: string; unit?: string; hint?: string }> = {
  variance_warn_pct: { label: 'Variance warning', unit: '%', hint: 'A gap this big between field weight and weighbridge is shown as a warning.' },
  variance_flag_pct: { label: 'Variance flag', unit: '%', hint: 'A gap this big is flagged for someone to look at.' },
  moisture_warn_pct: { label: 'Moisture warning', unit: '%', hint: 'Above this, the load is marked wet.' },
  default_outturn_ratio_pct: { label: 'Default outturn ratio', unit: '%', hint: 'Lint from seed cotton, used to estimate a heap output.' },
  default_bale_unit_kg: { label: 'Default bale weight', unit: 'kg' },
  default_shiv_pct: { label: 'Default shiv', unit: '%' },
  default_dust_pct: { label: 'Default dust', unit: '%' },
};

/** Delivery tolerances (Module 5) and heap defaults (Module 6), side by side. */
export default function DeliveryHeapPage() {
  return (
    <div className="flex flex-col gap-6">
      <ConfigBlock
        block="delivery"
        title="Delivery tolerances"
        description="When a weight difference or a moisture reading is worth a second look."
      />
      <ConfigBlock
        block="heap"
        title="Heap and batch defaults"
        description="The starting values a new heap takes. An open heap keeps the values it froze when it opened."
        notice="Changing these does not touch a heap that is already open: its ratio and bale weight were fixed at the moment it opened, so its expected output never moves under it."
      />
      <Card padding="md">
        <SectionHeader
          title="Fixed rules"
          description="Set in code because records depend on them. They are shown here so nobody looks for a switch that does not exist."
        />
        <div className="mt-3">
          <KeyValueList
            items={[
              { label: 'Maund', value: '40 kg', mono: true },
              { label: 'Acre', value: '4,046.86 m²', mono: true },
              { label: 'Hectare', value: '10,000 m²', mono: true },
              { label: 'Field boundaries', value: 'Must never overlap. Always enforced.' },
              { label: 'Submitted fieldbooks', value: 'Locked. A correction is a new record, never an edit.' },
            ]}
            columns={2}
          />
        </div>
      </Card>
    </div>
  );
}

function ConfigBlock({
  block,
  title,
  description,
  notice,
}: {
  block: string;
  title: string;
  description: string;
  notice?: string;
}) {
  const config = useConfigBlock<CropConfig>(block);
  const save = useSaveConfigBlock(block);
  const [draft, setDraft] = useState<Record<string, Record<string, number>>>({});

  useEffect(() => {
    if (config.data) setDraft(structuredClone(config.data.crops));
  }, [config.dataUpdatedAt]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = useMemo(
    () => config.data !== undefined && JSON.stringify(draft) !== JSON.stringify(config.data.crops),
    [draft, config.data],
  );

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader title={title} description={description} />
      {notice && (
        <p className="rounded-control bg-forest-50 px-3 py-2 text-sm text-ink">{notice}</p>
      )}

      {config.isLoading ? (
        <Skeleton className="h-40 w-full" shape="block" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {Object.entries(draft).map(([crop, values]) => (
            <Card key={crop} padding="md">
              <div className="flex items-center gap-2">
                <h3 className="text-base font-medium text-ink">{CROP_LABEL[crop] ?? crop}</h3>
                <ChangedMarker
                  changed={JSON.stringify(values) !== JSON.stringify(config.data?.crops[crop] ?? {})}
                />
              </div>
              <div className="mt-3 flex flex-col gap-3">
                {Object.entries(values).map(([name, number]) => (
                  <FormField
                    key={name}
                    label={LABELS[name]?.label ?? name.replace(/_/g, ' ')}
                    hint={LABELS[name]?.hint}
                  >
                    <NumberInput
                      value={number ?? null}
                      unit={LABELS[name]?.unit}
                      decimals={2}
                      onValueChange={(next) =>
                        setDraft((current) => ({
                          ...current,
                          [crop]: { ...current[crop], [name]: next ?? 0 },
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

      <StickySaveBar
        dirty={dirty}
        saving={save.isPending}
        message="These apply to new calculations. Records already made keep their values."
        onSave={() => save.mutate({ values: draft, version: config.data?.version })}
        onDiscard={() => config.data && setDraft(structuredClone(config.data.crops))}
      />
    </div>
  );
}
