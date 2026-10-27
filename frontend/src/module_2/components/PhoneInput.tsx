import { forwardRef } from 'react';
import { Phone } from 'lucide-react';
import { Input } from '@/design-system/components/Input';
import type { Crop } from '../api/types';
import { formatPhone } from '../format';

export interface PhoneInputProps {
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  crop: Crop;
  invalid?: boolean;
  disabled?: boolean;
  id?: string;
}

/**
 * Phone number, formatted for the programme's country as it is typed.
 *
 * Both international forms are accepted and normalised to the local one, so an officer
 * copying ``+92 300 1234567`` from a message ends up with ``0300-1234567`` without
 * having to retype it.
 */
export const PhoneInput = forwardRef<HTMLInputElement, PhoneInputProps>(function PhoneInput(
  { value, onChange, onBlur, crop, invalid, disabled, id },
  ref,
) {
  return (
    <Input
      ref={ref}
      id={id}
      type="tel"
      mono
      inputMode="tel"
      autoComplete="tel"
      placeholder={crop === 'cotton' ? '0300-1234567' : '07700 900123'}
      leadingIcon={<Phone />}
      value={value}
      invalid={invalid}
      disabled={disabled}
      onBlur={onBlur}
      onChange={(event) => onChange(formatPhone(event.target.value, crop))}
    />
  );
});
