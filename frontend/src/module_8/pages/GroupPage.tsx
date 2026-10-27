import { useEffect, useState } from 'react';
import { ApiError } from '@/core/api/errors';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { Skeleton } from '@/design-system/components/Skeleton';
import type { Setting } from '../api/types';
import { HistoryDrawer } from '../components/HistoryDrawer';
import { SettingCard } from '../components/SettingCard';
import { StickySaveBar } from '../components/StickySaveBar';
import { useResetSetting, useSaveSetting, useSettingsRegistry } from '../hooks/useSettings';

export interface GroupPageProps {
  group: string;
  title: string;
  description: string;
  /** Shown above the settings, for a rule the screen cannot change. */
  notice?: React.ReactNode;
  children?: React.ReactNode;
}

/**
 * One group of generic settings, rendered from the registry.
 *
 * Several screens (validation rules, alerts, map, QR) are exactly this: the settings of
 * one group, each with its own control, history and reset. They share this page rather
 * than repeating the save, dirty-state and conflict handling four times.
 */
export function GroupPage({ group, title, description, notice, children }: GroupPageProps) {
  const registry = useSettingsRegistry(group);
  const save = useSaveSetting();
  const reset = useResetSetting();
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [historyKey, setHistoryKey] = useState<string | null>(null);

  const items = registry.data?.items ?? [];

  useEffect(() => {
    setDraft(Object.fromEntries(items.map((item) => [item.key, item.value])));
    // Only when the server's values change, so typing is never overwritten.
  }, [registry.dataUpdatedAt]); // eslint-disable-line react-hooks/exhaustive-deps

  const changed = items.filter(
    (item) => JSON.stringify(draft[item.key]) !== JSON.stringify(item.value),
  );

  const saveAll = async () => {
    const failures: Record<string, string> = {};
    for (const item of changed) {
      try {
        await save.mutateAsync({
          key: item.key,
          value: draft[item.key],
          version: item.version,
        });
      } catch (error) {
        failures[item.key] = error instanceof ApiError ? error.message : 'Could not be saved.';
      }
    }
    setErrors(failures);
  };

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader title={title} description={description} />
      {notice}
      {children}

      {registry.isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-28 w-full" shape="block" />
          <Skeleton className="h-28 w-full" shape="block" />
        </div>
      ) : items.length === 0 ? (
        <Card padding="md">
          <p className="text-base text-muted">There is nothing to change in this section.</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((item: Setting) => (
            <SettingCard
              key={item.key}
              setting={item}
              value={draft[item.key]}
              error={errors[item.key]}
              onChange={(value) => setDraft((current) => ({ ...current, [item.key]: value }))}
              onReset={() => reset.mutate(item.key)}
              onShowHistory={() => setHistoryKey(item.key)}
            />
          ))}
        </div>
      )}

      <StickySaveBar
        dirty={changed.length > 0}
        saving={save.isPending}
        message={`${changed.length} setting${changed.length === 1 ? '' : 's'} changed.`}
        onSave={() => void saveAll()}
        onDiscard={() =>
          setDraft(Object.fromEntries(items.map((item) => [item.key, item.value])))
        }
      />

      <HistoryDrawer
        settingKey={historyKey}
        label={items.find((item) => item.key === historyKey)?.label}
        onClose={() => setHistoryKey(null)}
      />
    </div>
  );
}
