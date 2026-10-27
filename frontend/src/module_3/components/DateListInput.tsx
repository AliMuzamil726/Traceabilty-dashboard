import { Plus, X } from 'lucide-react';
import { Button, DatePicker, IconButton } from '@/design-system/components';

export interface DateListInputProps {
  value: (string | null)[] | null | undefined;
  onChange: (value: (string | null)[]) => void;
  label: string;
  max?: string;
  disabled?: boolean;
}

/** A growing list of dates (retting turns). Each date can be removed on its own. */
export function DateListInput({ value, onChange, label, max, disabled }: DateListInputProps) {
  const dates = value ?? [];
  return (
    <div role="group" aria-label={label} className="flex flex-col gap-2">
      {dates.map((date, i) => (
        <div key={i} className="flex items-center gap-2">
          <DatePicker
            value={date}
            max={max}
            disabled={disabled}
            aria-label={`${label} ${i + 1}`}
            onValueChange={(next) => onChange(dates.map((d, j) => (j === i ? next : d)))}
          />
          {!disabled && (
            <IconButton
              label={`Remove ${label.toLowerCase()} ${i + 1}`}
              icon={<X className="h-4 w-4" />}
              onClick={() => onChange(dates.filter((_, j) => j !== i))}
            />
          )}
        </div>
      ))}
      {!disabled && (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => onChange([...dates, null])}
          className="self-start"
        >
          Add date
        </Button>
      )}
    </div>
  );
}
