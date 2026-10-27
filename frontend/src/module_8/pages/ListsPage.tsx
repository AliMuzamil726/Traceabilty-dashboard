import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { cn } from '@/core/utils/cn';
import { Badge } from '@/design-system/components/Badge';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { Skeleton } from '@/design-system/components/Skeleton';
import { settingsApi, settingsKeys } from '../api/client';
import { ListManager } from '../components/ListManager';

const GROUP_LABEL: Record<string, string> = {
  cotton: 'Cotton',
  hemp: 'Hemp',
  shared: 'Shared',
};

/** The dropdown lists every form reads its options from. */
export default function ListsPage() {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<string | null>(null);

  const lists = useQuery({
    queryKey: settingsKeys.lists,
    queryFn: ({ signal }) => settingsApi.lists(signal),
  });

  const current = selected ?? lists.data?.[0]?.key ?? null;
  const values = useQuery({
    queryKey: settingsKeys.listValues(current ?? ''),
    queryFn: ({ signal }) => settingsApi.listValues(current as string, signal),
    enabled: current !== null,
  });

  const filtered = (lists.data ?? []).filter((list) =>
    list.label.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const grouped = Object.entries(
    filtered.reduce<Record<string, typeof filtered>>((groups, list) => {
      (groups[list.group] ??= []).push(list);
      return groups;
    }, {}),
  );

  const selectedList = (lists.data ?? []).find((list) => list.key === current);

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="Dropdown lists"
        description="The options officers choose from. Every record stores the key, so a label can always be corrected."
      />
      <p className="rounded-control bg-forest-50 px-3 py-2 text-sm text-ink">
        A list exists because a form step refers to it, so lists themselves cannot be added or
        removed here. What each list is used by is shown above its values.
      </p>

      <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
        <Card padding="sm" className="h-fit">
          <FormField label="Search lists" hideLabel>
            <Input
              value={search}
              placeholder="Search lists"
              onChange={(event) => setSearch(event.target.value)}
            />
          </FormField>
          {lists.isLoading ? (
            <div className="mt-3 flex flex-col gap-2">
              <Skeleton className="h-8 w-full" shape="block" />
              <Skeleton className="h-8 w-full" shape="block" />
            </div>
          ) : (
            <div className="mt-3 flex max-h-[32rem] flex-col gap-4 overflow-auto">
              {grouped.map(([group, items]) => (
                <div key={group}>
                  <p className="mb-1 px-2 text-xs font-medium uppercase tracking-wide text-muted">
                    {GROUP_LABEL[group] ?? group}
                  </p>
                  <ul className="flex flex-col gap-0.5">
                    {items.map((list) => (
                      <li key={list.key}>
                        <button
                          type="button"
                          onClick={() => setSelected(list.key)}
                          aria-current={list.key === current}
                          className={cn(
                            'flex w-full items-center justify-between gap-2 rounded-control px-2 py-1.5 text-left text-base',
                            list.key === current
                              ? 'bg-forest-50 font-medium text-forest-800'
                              : 'hover:bg-canvas',
                          )}
                        >
                          <span className="min-w-0 truncate">{list.label}</span>
                          <Badge tone="neutral" size="sm">
                            {list.active_values}
                          </Badge>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </Card>

        <div className="min-w-0">
          {selectedList ? (
            <ListManager
              list={selectedList}
              values={values.data ?? []}
              loading={values.isLoading}
              onChanged={() => void values.refetch()}
            />
          ) : (
            <Card padding="md">
              <p className="text-base text-muted">Choose a list to see its values.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
