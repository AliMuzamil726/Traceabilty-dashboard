import { NumberInput } from '@/design-system/components';
import type { FieldPart } from '../api/types';

export interface PairedNumberInputProps {
  parts: FieldPart[];
  value: Record<string, number | null> | null | undefined;
  onChange: (value: Record<string, number | null>) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
  label: string;
}

/** Two or three related numbers (P2O5 / K2O, N / P2O5 / K2O) entered side by side. */
export function PairedNumberInput({
  parts,
  value,
  onChange,
  errors = {},
  disabled,
  label,
}: PairedNumberInputProps) {
  const current = value ?? {};
  return (
    <div
      role="group"
      aria-label={label}
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3"
    >
      {parts.map((part) => (
        <label
          key={part.key}
          className="flex min-w-0 flex-col gap-1.5 rounded-control border border-line bg-surface p-2.5 text-xs font-medium text-muted"
        >
          <span className="text-ink">{part.label}</span>
          <NumberInput
            value={current[part.key] ?? null}
            onValueChange={(n) => onChange({ ...current, [part.key]: n })}
            unit={part.unit}
            min={part.min}
            max={part.max}
            disabled={disabled}
            invalid={Boolean(errors[part.key])}
            aria-label={`${label}: ${part.label}`}
          />
        </label>
      ))}
    </div>
  );
}
