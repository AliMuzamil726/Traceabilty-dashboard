import { CalendarDays } from 'lucide-react';
import { forwardRef, type InputHTMLAttributes } from 'react';
import { Input } from './Input';

export interface DatePickerProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'value' | 'onChange' | 'min' | 'max'> {
  /** ISO date YYYY-MM-DD or null. */
  value: string | null;
  onValueChange: (value: string | null) => void;
  min?: string;
  max?: string;
  invalid?: boolean;
}

/**
 * Date field built on the native date input: full keyboard support, a localised
 * calendar on every platform (including Android tablets in the field) and ISO values.
 */
export const DatePicker = forwardRef<HTMLInputElement, DatePickerProps>(function DatePicker(
  { value, onValueChange, ...rest },
  ref,
) {
  return (
    <Input
      ref={ref}
      type="date"
      value={value ?? ''}
      onChange={(e) => onValueChange(e.target.value || null)}
      leadingIcon={<CalendarDays />}
      className="tabular"
      {...rest}
    />
  );
});
