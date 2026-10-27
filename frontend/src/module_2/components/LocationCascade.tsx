import { useId, useMemo } from 'react';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { Select } from '@/design-system/components/Select';
import { useDistricts, useProvinces, useTehsils, useVillageSuggestions } from '../hooks/useLocations';
import { TEHSIL_OTHER } from '../api/schemas';

export interface LocationValue {
  province_code: string;
  district_code: string;
  tehsil_code: string;
  tehsil_name: string;
  village: string;
}

export interface LocationCascadeProps {
  value: LocationValue;
  onChange: (next: LocationValue) => void;
  country: string;
  errors?: Partial<Record<keyof LocationValue, string>>;
  disabled?: boolean;
}

/**
 * Province to district to tehsil, then a typed village.
 *
 * The rule that makes a cascade trustworthy is that choosing a level clears every
 * level below it. Without that, picking Punjab then Multan then switching to Sindh
 * would leave Multan selected under Sindh and the farmer would be filed in a district
 * that does not exist in their province. Each level is also disabled until the one
 * above it is chosen, so the officer cannot get into that state in the first place.
 *
 * Villages are never a list: there are tens of thousands and any list goes stale. The
 * officer types the village, and the suggestions are what other officers already typed
 * in that tehsil, which makes spellings converge without freezing them.
 */
export function LocationCascade({
  value,
  onChange,
  country,
  errors = {},
  disabled,
}: LocationCascadeProps) {
  const villageListId = `villages${useId().replace(/:/g, '')}`;
  const provinces = useProvinces(country);
  const districts = useDistricts(value.province_code || null, country);
  const tehsils = useTehsils(value.district_code || null, country);

  const tehsilOptions = useMemo(() => {
    const items = (tehsils.data?.items ?? []).map((t) => ({ value: t.value, label: t.label }));
    // Always offered: many districts have no seeded tehsil list at all.
    return [...items, { value: TEHSIL_OTHER, label: 'Other (type manually)' }];
  }, [tehsils.data]);

  const chosenTehsilName = useMemo(() => {
    if (value.tehsil_code === TEHSIL_OTHER || !value.tehsil_code) return null;
    return tehsils.data?.items.find((t) => t.value === value.tehsil_code)?.label ?? null;
  }, [tehsils.data, value.tehsil_code]);

  const manualTehsil = value.tehsil_code === TEHSIL_OTHER;
  const villageTehsil = manualTehsil ? value.tehsil_name || null : chosenTehsilName;
  const villages = useVillageSuggestions(villageTehsil, value.village);

  return (
    <>
      <FormField label="Province" required error={errors.province_code}>
        <Select
          placeholder={provinces.isLoading ? 'Loading provinces' : 'Choose a province'}
          disabled={disabled || provinces.isLoading}
          options={(provinces.data?.items ?? []).map((p) => ({ value: p.value, label: p.label }))}
          value={value.province_code}
          onChange={(event) =>
            // Choosing a province invalidates the district, tehsil and village below it.
            onChange({
              province_code: event.target.value,
              district_code: '',
              tehsil_code: '',
              tehsil_name: '',
              village: '',
            })
          }
        />
      </FormField>

      <FormField
        label="District"
        required
        error={errors.district_code}
        hint={!value.province_code ? 'Choose a province first' : undefined}
      >
        <Select
          placeholder={districts.isLoading ? 'Loading districts' : 'Choose a district'}
          disabled={disabled || !value.province_code || districts.isLoading}
          options={(districts.data?.items ?? []).map((d) => ({ value: d.value, label: d.label }))}
          value={value.district_code}
          onChange={(event) =>
            onChange({
              ...value,
              district_code: event.target.value,
              tehsil_code: '',
              tehsil_name: '',
              village: '',
            })
          }
        />
      </FormField>

      <FormField
        label="Tehsil or city"
        required
        error={errors.tehsil_code ?? errors.tehsil_name}
        hint={!value.district_code ? 'Choose a district first' : undefined}
      >
        <Select
          placeholder={tehsils.isLoading ? 'Loading tehsils' : 'Choose a tehsil or city'}
          disabled={disabled || !value.district_code || tehsils.isLoading}
          options={tehsilOptions}
          value={value.tehsil_code}
          onChange={(event) =>
            onChange({
              ...value,
              tehsil_code: event.target.value,
              tehsil_name: '',
              village: '',
            })
          }
        />
      </FormField>

      {manualTehsil && (
        <FormField label="Tehsil or city name" required error={errors.tehsil_name}>
          <Input
            placeholder="Type the tehsil or city"
            disabled={disabled}
            value={value.tehsil_name}
            onChange={(event) => onChange({ ...value, tehsil_name: event.target.value })}
          />
        </FormField>
      )}

      <FormField
        label="Village or town"
        required
        error={errors.village}
        hint="Type the name. Suggestions come from villages already entered in this tehsil."
      >
        {/*
          A free text field with suggestions attached, not a picker: the village must
          be typeable even when nobody has entered it before, which a select or a
          combobox that only commits list choices would prevent.
        */}
        <Input
          placeholder="Type a village or town"
          autoComplete="off"
          list={villageListId}
          disabled={disabled || !villageTehsil}
          value={value.village}
          onChange={(event) => onChange({ ...value, village: event.target.value })}
        />
        <datalist id={villageListId}>
          {(villages.data ?? []).map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      </FormField>
    </>
  );
}
