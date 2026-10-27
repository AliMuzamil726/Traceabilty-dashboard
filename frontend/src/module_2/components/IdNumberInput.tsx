import { forwardRef } from 'react';
import { CreditCard } from 'lucide-react';
import { Input } from '@/design-system/components/Input';
import type { Crop } from '../api/types';
import { formatIdNumber } from '../format';

export interface IdNumberInputProps {
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  crop: Crop;
  invalid?: boolean;
  disabled?: boolean;
  id?: string;
}

/**
 * The ID number field, masked as the officer types.
 *
 * Cotton shows a CNIC as ``12345-1234567-1``; hemp groups the digits in threes. The
 * formatter runs on the whole value every keystroke rather than appending separators,
 * which is what makes pasting an unformatted string work: the paste is reformatted
 * exactly like typed input, and deleting a separator deletes the digit beside it
 * instead of leaving the field in a shape the mask cannot produce.
 */
export const IdNumberInput = forwardRef<HTMLInputElement, IdNumberInputProps>(
  function IdNumberInput({ value, onChange, onBlur, crop, invalid, disabled, id }, ref) {
    const placeholder = crop === 'cotton' ? '12345-1234567-1' : '123 456 789';
    return (
      <Input
        ref={ref}
        id={id}
        mono
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        placeholder={placeholder}
        aria-describedby={undefined}
        leadingIcon={<CreditCard />}
        value={value}
        invalid={invalid}
        disabled={disabled}
        onBlur={onBlur}
        onChange={(event) => onChange(formatIdNumber(event.target.value, crop))}
      />
    );
  },
);
