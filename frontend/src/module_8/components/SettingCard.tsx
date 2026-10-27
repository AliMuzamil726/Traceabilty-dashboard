import { History, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { formatDateTime } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Card } from '@/design-system/components/Card';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { NumberInput } from '@/design-system/components/NumberInput';
import { Select } from '@/design-system/components/Select';
import { Switch } from '@/design-system/components/Switch';
import { Textarea } from '@/design-system/components/Textarea';
import type { Setting } from '../api/types';
import { ChangedMarker } from './StickySaveBar';

export interface SettingCardProps {
  setting: Setting;
  value: unknown;
  onChange: (value: unknown) => void;
  onReset: () => void;
  onShowHistory: () => void;
  error?: string;
  /** Hide the description when the surrounding card already explains the group. */
  compact?: boolean;
}

/**
 * One setting, rendered from its declaration rather than from a hand-written form.
 *
 * The registry says what a setting is (a number with a range, a choice, a flag, a small
 * object), so adding one to the backend gives it a usable control here with no second
 * edit. A value from ``.env`` or a default is marked, because "where did this number
 * come from" is the first question an administrator asks.
 */
export function SettingCard({
  setting,
  value,
  onChange,
  onReset,
  onShowHistory,
  error,
  compact,
}: SettingCardProps) {
  const changed = JSON.stringify(value) !== JSON.stringify(setting.value);
  const isDefault = JSON.stringify(value) === JSON.stringify(setting.default);

  return (
    <Card padding="md" className="min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-medium text-ink">{setting.label}</h3>
            <ChangedMarker changed={changed} />
            {setting.needs_restart && <Badge tone="warning">Needs a restart</Badge>}
            {setting.source === 'env' && <Badge tone="neutral">From .env</Badge>}
          </div>
          {!compact && <p className="mt-0.5 text-sm text-muted">{setting.description}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={onShowHistory}
            leftIcon={<History className="h-4 w-4" aria-hidden />}
          >
            History
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            disabled={isDefault}
            leftIcon={<RotateCcw className="h-4 w-4" aria-hidden />}
          >
            Reset
          </Button>
        </div>
      </div>

      <div className="mt-3 max-w-xl">
        <SettingControl setting={setting} value={value} onChange={onChange} error={error} />
      </div>

      <p className="mt-2 text-xs text-muted">
        {setting.read_by.length > 0 && <>Read by {setting.read_by.join(', ')}. </>}
        {setting.changed_at ? (
          <>Last changed {formatDateTime(setting.changed_at)}.</>
        ) : (
          <>Never changed; this is the value the product ships with.</>
        )}
      </p>
    </Card>
  );
}

function SettingControl({
  setting,
  value,
  onChange,
  error,
}: Pick<SettingCardProps, 'setting' | 'value' | 'onChange' | 'error'>) {
  if (setting.sensitive) {
    return <p className="text-sm text-muted">This value is hidden and cannot be shown here.</p>;
  }

  if (setting.type === 'bool') {
    return (
      <Switch
        checked={Boolean(value)}
        onChange={onChange}
        label={setting.label}
        hideLabel
        description={error}
      />
    );
  }

  if (setting.type === 'choice' && setting.choices) {
    return (
      <FormField label={setting.label} hideLabel error={error}>
        <Select
          value={String(value ?? '')}
          onChange={(event) => onChange(event.target.value)}
          options={setting.choices.map((choice) => ({
            value: String(choice),
            label: String(choice).replace(/_/g, ' '),
          }))}
        />
      </FormField>
    );
  }

  if (setting.type === 'int' || setting.type === 'float') {
    return (
      <FormField
        label={setting.label}
        hideLabel
        error={error}
        hint={rangeHint(setting)}
      >
        <NumberInput
          value={typeof value === 'number' ? value : null}
          onValueChange={(next) => onChange(next)}
          decimals={setting.type === 'float' ? 2 : 0}
          min={setting.minimum ?? undefined}
          max={setting.maximum ?? undefined}
        />
      </FormField>
    );
  }

  if (setting.type === 'json') {
    return <JsonField setting={setting} value={value} onChange={onChange} error={error} />;
  }

  return (
    <FormField label={setting.label} hideLabel error={error}>
      <Input value={String(value ?? '')} onChange={(event) => onChange(event.target.value)} />
    </FormField>
  );
}

function rangeHint(setting: Setting): string | undefined {
  if (setting.minimum !== null && setting.maximum !== null) {
    return `Between ${setting.minimum} and ${setting.maximum}.`;
  }
  if (setting.minimum !== null) return `At least ${setting.minimum}.`;
  if (setting.maximum !== null) return `At most ${setting.maximum}.`;
  return undefined;
}

/** A small object (a label grid, the map centres) edited as JSON, checked as you type. */
function JsonField({
  setting,
  value,
  onChange,
  error,
}: Pick<SettingCardProps, 'setting' | 'value' | 'onChange' | 'error'>) {
  const [text, setText] = useState(() => JSON.stringify(value ?? setting.default, null, 2));
  const [parseError, setParseError] = useState<string | undefined>(undefined);

  return (
    <FormField
      label={setting.label}
      hideLabel
      error={error ?? parseError}
      hint="One value per line, in JSON."
    >
      <Textarea
        value={text}
        rows={Math.min(12, text.split('\n').length + 1)}
        className="mono-id text-sm"
        onChange={(event) => {
          const next = event.target.value;
          setText(next);
          try {
            onChange(JSON.parse(next));
            setParseError(undefined);
          } catch {
            setParseError('This is not valid JSON yet, so it has not been applied.');
          }
        }}
      />
    </FormField>
  );
}
