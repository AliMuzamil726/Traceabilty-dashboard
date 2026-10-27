import { CheckCircle2, Loader2, MapPin, TriangleAlert } from 'lucide-react';
import { useEffect } from 'react';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { usePostcode } from '../hooks/usePostcode';
import { formatPostcode } from '../format';

export interface PostcodeValue {
  postcode: string;
  county: string;
  region: string;
}

export interface PostcodeLookupProps {
  value: PostcodeValue;
  onChange: (next: PostcodeValue) => void;
  /** Told when manual entry opens, so the form can require county and region. */
  onManualChange?: (manual: boolean) => void;
  errors?: Partial<Record<keyof PostcodeValue, string>>;
  disabled?: boolean;
}

/**
 * Postcode, with the county and region filled in from it.
 *
 * County and region are read-only while anything can resolve the postcode, so the two
 * cannot drift apart. They open for editing in exactly one case: the lookup failed and
 * the fallback table had nothing either. The officer is told that is why, rather than
 * being handed two mysteriously editable fields.
 */
export function PostcodeLookup({
  value,
  onChange,
  onManualChange,
  errors = {},
  disabled,
}: PostcodeLookupProps) {
  const lookup = usePostcode(value.postcode);
  const found = lookup.data;
  const manual = found?.editable === true;

  useEffect(() => {
    onManualChange?.(manual);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manual]);

  useEffect(() => {
    if (!found || found.editable) return;
    const county = found.county ?? '';
    const region = found.region ?? '';
    if (county === value.county && region === value.region) return;
    onChange({ ...value, county, region });
    // Only react to a new answer; `value` and `onChange` would re-fire this constantly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [found]);

  const status = (() => {
    if (lookup.isFetching) {
      return (
        <span className="flex items-center gap-1.5 text-sm text-muted">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
          Looking up the postcode
        </span>
      );
    }
    if (manual) {
      return (
        <span className="flex items-center gap-1.5 text-sm text-wheat-600">
          <TriangleAlert className="h-3.5 w-3.5" aria-hidden />
          The postcode could not be looked up. Enter the county and region.
        </span>
      );
    }
    if (found) {
      return (
        <span className="flex items-center gap-1.5 text-sm text-forest-800">
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
          County and region filled in from the postcode
        </span>
      );
    }
    return null;
  })();

  return (
    <>
      <FormField
        label="Postcode"
        required
        error={errors.postcode}
        hint="The county and region are filled in from this"
      >
        <Input
          mono
          autoComplete="postal-code"
          placeholder="CB23 6DP"
          leadingIcon={<MapPin />}
          disabled={disabled}
          value={value.postcode}
          onChange={(event) =>
            onChange({ ...value, postcode: formatPostcode(event.target.value) })
          }
        />
      </FormField>

      <div className="flex items-end" aria-live="polite">
        {status}
      </div>

      <FormField label="County" required={manual} error={errors.county}>
        <Input
          readOnly={!manual}
          disabled={disabled}
          placeholder={manual ? 'Type the county' : 'From the postcode'}
          value={value.county}
          onChange={(event) => onChange({ ...value, county: event.target.value })}
        />
      </FormField>

      <FormField label="Region" required={manual} error={errors.region}>
        <Input
          readOnly={!manual}
          disabled={disabled}
          placeholder={manual ? 'Type the region' : 'From the postcode'}
          value={value.region}
          onChange={(event) => onChange({ ...value, region: event.target.value })}
        />
      </FormField>
    </>
  );
}
