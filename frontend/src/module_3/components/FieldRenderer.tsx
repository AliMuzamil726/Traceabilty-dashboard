import { Lightbulb } from 'lucide-react';
import type { ReactNode } from 'react';
import { useMasterList } from '@/core/hooks/useSharedData';
import { cn } from '@/core/utils/cn';
import { DatePicker, FormField, Input, NumberInput, Select } from '@/design-system/components';
import type { FieldDef } from '../api/types';
import { DateListInput } from './DateListInput';
import { PairedNumberInput } from './PairedNumberInput';

export interface FieldRendererProps {
  field: FieldDef;
  value: unknown;
  onChange: (value: unknown) => void;
  country: string;
  crop: string;
  error?: string;
  /** Part errors for paired numbers, keyed by part (from "field.part" paths). */
  partErrors?: Record<string, string>;
  warning?: string;
  /** A value the step's suggestion map proposes; offered, never forced. */
  suggestion?: unknown;
  readOnly?: boolean;
  /** Rendered for the photos field type, which belongs to the whole fieldbook. */
  photos?: ReactNode;
}

const today = () => new Date().toISOString().slice(0, 10);

function hintFor(field: FieldDef, warning?: string): ReactNode {
  if (warning) return <span className="text-wheat-600">{warning}</span>;
  return field.help;
}

/** Options for list-backed fields, always from the master lists. */
function useOptions(field: FieldDef, country: string, crop: string) {
  const list = useMasterList(field.list_key ?? '', { country, crop });
  return field.list_key ? (list.data?.items ?? []).map((o) => ({ value: o.value, label: o.label })) : [];
}

function SuggestionButton({ field, suggestion, onApply }: { field: FieldDef; suggestion: unknown; onApply: () => void }) {
  const text =
    typeof suggestion === 'number'
      ? `${suggestion}${field.unit ? ` ${field.unit}` : ''}`
      : Object.entries(suggestion as Record<string, number>)
          .map(([k, v]) => `${field.parts?.find((p) => p.key === k)?.label ?? k} ${v}`)
          .join(', ');
  return (
    <button
      type="button"
      onClick={onApply}
      className="inline-flex items-center gap-1 self-start text-xs font-medium text-forest-700 hover:text-forest-900"
    >
      <Lightbulb className="h-3.5 w-3.5" aria-hidden />
      Use typical value: {text}
    </button>
  );
}

/** One schema field. Every control type the form definitions use is handled here. */
export function FieldRenderer(props: FieldRendererProps) {
  const { field, value, onChange, country, crop, error, partErrors, warning, suggestion, readOnly, photos } = props;
  const options = useOptions(field, country, crop);
  const locked = readOnly || field.readonly || Boolean(field.computed);

  if (field.type === 'photos') {
    return (
      <FormField label={field.label} hint={field.help}>
        <div>{photos}</div>
      </FormField>
    );
  }

  let control: ReactNode;
  switch (field.type) {
    case 'text':
      control = (
        <Input
          value={typeof value === 'string' ? value : value == null ? '' : String(value)}
          onChange={(e) => onChange(e.target.value)}
          readOnly={locked}
          maxLength={200}
        />
      );
      break;
    case 'number':
      control = (
        <NumberInput
          value={typeof value === 'number' ? value : null}
          onValueChange={onChange}
          unit={field.unit}
          min={field.min}
          max={field.max}
          decimals={field.integer ? 0 : undefined}
          readOnly={locked}
          invalid={Boolean(error)}
        />
      );
      break;
    case 'date':
      control = (
        <DatePicker
          value={typeof value === 'string' ? value : null}
          onValueChange={onChange}
          max={field.not_future ? today() : undefined}
          readOnly={locked}
          invalid={Boolean(error)}
        />
      );
      break;
    case 'dates':
      control = (
        <DateListInput
          value={Array.isArray(value) ? (value as (string | null)[]) : []}
          onChange={onChange}
          label={field.label}
          max={today()}
          disabled={locked}
        />
      );
      break;
    case 'select':
      control = (
        <Select
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value || null)}
          options={options}
          placeholder="Choose"
          disabled={locked}
          invalid={Boolean(error)}
        />
      );
      break;
    case 'multiselect': {
      const chosen = Array.isArray(value) ? (value as string[]) : [];
      control = (
        <div role="group" aria-label={field.label} className="flex flex-wrap gap-2">
          {options.map((o) => {
            const on = chosen.includes(o.value);
            return (
              <label
                key={o.value}
                className={cn(
                  'flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm',
                  on ? 'border-forest-600 bg-forest-50 text-forest-900' : 'border-line bg-surface text-ink',
                  locked && 'cursor-default opacity-70',
                )}
              >
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-forest-700"
                  checked={on}
                  disabled={locked}
                  onChange={() => onChange(on ? chosen.filter((v) => v !== o.value) : [...chosen, o.value])}
                />
                {o.label}
              </label>
            );
          })}
        </div>
      );
      break;
    }
    case 'yesno':
      control = (
        <div role="radiogroup" aria-label={field.label} className="flex gap-2">
          {options.map((o) => (
            <label
              key={o.value}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium',
                value === o.value ? 'border-forest-600 bg-forest-50 text-forest-900' : 'border-line bg-surface text-ink',
              )}
            >
              <input
                type="radio"
                className="h-4 w-4 accent-forest-700"
                name={field.key}
                value={o.value}
                checked={value === o.value}
                disabled={locked}
                onChange={() => onChange(o.value)}
              />
              {o.label}
            </label>
          ))}
        </div>
      );
      break;
    case 'paired_number':
      control = (
        <PairedNumberInput
          parts={field.parts ?? []}
          value={(value as Record<string, number | null>) ?? null}
          onChange={onChange}
          errors={partErrors}
          disabled={locked}
          label={field.label}
        />
      );
      break;
    default:
      control = null;
  }

  const showSuggestion =
    !locked &&
    suggestion !== undefined &&
    JSON.stringify(suggestion) !== JSON.stringify(value);

  return (
    <FormField
      label={field.label}
      required={Boolean(field.required) && !locked}
      error={error ?? Object.values(partErrors ?? {})[0]}
      hint={hintFor(field, warning)}
    >
      <div className="flex min-w-0 flex-col gap-1.5">
        {control}
        {showSuggestion && <SuggestionButton field={field} suggestion={suggestion} onApply={() => onChange(suggestion)} />}
      </div>
    </FormField>
  );
}
