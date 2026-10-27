import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown, UserCog } from 'lucide-react';
import { useId, useMemo } from 'react';
import type { Officer } from '@/core/api/types';
import { useOfficers } from '@/core/hooks/useSharedData';
import { useOfficerStore } from '@/core/store/officerStore';
import { countryName } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { Tooltip } from '@/design-system/components/Tooltip';

function optionLabel(o: Officer): string {
  if (o.role === 'admin') return `${o.full_name} (Administrator)`;
  return o.field_office ? `${o.full_name} (${o.field_office.name})` : o.full_name;
}

/**
 * Development tool: choose which officer the app acts as. The choice is stored in
 * officerStore and sent as the X-Officer-Id header on every request. Replaced by
 * real sign-in later.
 */
export function OfficerSwitcher() {
  const id = `officer-switch${useId().replace(/:/g, '')}`;
  const queryClient = useQueryClient();
  const officerId = useOfficerStore((s) => s.officerId);
  const setOfficer = useOfficerStore((s) => s.setOfficer);
  const { data, isLoading, isError } = useOfficers();

  const groups = useMemo(() => {
    const items = data?.items ?? [];
    const admins = items.filter((o) => o.role === 'admin');
    const byCountry = new Map<string, Officer[]>();
    for (const o of items.filter((x) => x.role !== 'admin')) {
      byCountry.set(o.country, [...(byCountry.get(o.country) ?? []), o]);
    }
    return { admins, byCountry: [...byCountry.entries()] };
  }, [data]);

  const onChange = (value: string) => {
    setOfficer(value || null);
    // Everything officer-scoped must be refetched as the new officer.
    void queryClient.invalidateQueries();
  };

  return (
    <div className="hidden items-center gap-2 sm:flex">
      <Tooltip content="Development tool: switch the acting officer">
        <span>
          <Badge size="sm" tone="accent">
            Dev
          </Badge>
        </span>
      </Tooltip>
      <label htmlFor={id} className="sr-only">
        Acting officer (development)
      </label>
      <div className="relative">
        <UserCog className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
        <select
          id={id}
          value={officerId ?? ''}
          disabled={isLoading || isError}
          onChange={(e) => onChange(e.target.value)}
          className="h-9 w-48 appearance-none truncate rounded-control border border-line bg-surface pl-8 pr-8 text-sm text-ink hover:border-forest-500/40 disabled:cursor-not-allowed disabled:text-muted lg:w-56"
        >
          <option value="">{isError ? 'Officers unavailable' : 'Default officer'}</option>
          {groups.admins.length > 0 && (
            <optgroup label="Administrators">
              {groups.admins.map((o) => (
                <option key={o.id} value={o.id}>
                  {optionLabel(o)}
                </option>
              ))}
            </optgroup>
          )}
          {groups.byCountry.map(([country, officers]) => (
            <optgroup key={country} label={countryName(country)}>
              {officers.map((o) => (
                <option key={o.id} value={o.id}>
                  {optionLabel(o)}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
      </div>
    </div>
  );
}
