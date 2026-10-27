import { useEffect, useState } from 'react';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { FormField } from '@/design-system/components/FormField';
import { SegmentedControl } from '@/design-system/components/SegmentedControl';
import { Skeleton } from '@/design-system/components/Skeleton';
import { Switch } from '@/design-system/components/Switch';
import type { Preferences } from '../api/types';
import { StickySaveBar } from '../components/StickySaveBar';
import { usePreferences, useSavePreferences } from '../hooks/useSettings';

/**
 * Personal display choices, for every officer rather than administrators only.
 *
 * Nothing here affects anybody else's work or any record, which is why this one screen
 * sits inside Settings without the administrator gate.
 */
export default function PreferencesPage() {
  const preferences = usePreferences();
  const save = useSavePreferences();
  const [draft, setDraft] = useState<Preferences | null>(null);

  useEffect(() => {
    if (preferences.data) setDraft(preferences.data);
  }, [preferences.dataUpdatedAt]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty =
    draft !== null &&
    preferences.data !== undefined &&
    JSON.stringify(draft) !== JSON.stringify(preferences.data);

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="My preferences"
        description="How the product looks for you. Nobody else is affected."
      />

      {preferences.isLoading || !draft ? (
        <Skeleton className="h-48 w-full" shape="block" />
      ) : (
        <Card padding="md">
          <div className="flex flex-col gap-5">
            <Switch
              checked={draft.sidebar_collapsed}
              onChange={(sidebar_collapsed) => setDraft({ ...draft, sidebar_collapsed })}
              label="Start with the sidebar collapsed"
              description="More room for tables and maps on a small screen."
            />

            <FormField
              label="Table density"
              hint="Compact fits more rows on screen; comfortable is easier to read."
            >
              <SegmentedControl
                aria-label="Table density"
                value={draft.table_density}
                onChange={(table_density) => setDraft({ ...draft, table_density })}
                options={[
                  { value: 'comfortable', label: 'Comfortable' },
                  { value: 'compact', label: 'Compact' },
                ]}
              />
            </FormField>

            <FormField label="Default crop" hint="Which crop screens open on.">
              <SegmentedControl
                aria-label="Default crop"
                value={draft.default_crop}
                onChange={(default_crop) => setDraft({ ...draft, default_crop })}
                options={[
                  { value: 'all', label: 'All crops' },
                  { value: 'cotton', label: 'Cotton' },
                  { value: 'hemp', label: 'Hemp' },
                ]}
              />
            </FormField>
          </div>
        </Card>
      )}

      <StickySaveBar
        dirty={dirty}
        saving={save.isPending}
        message="Your preferences have changed."
        onSave={() => draft && save.mutate(draft)}
        onDiscard={() => preferences.data && setDraft(preferences.data)}
      />
    </div>
  );
}
