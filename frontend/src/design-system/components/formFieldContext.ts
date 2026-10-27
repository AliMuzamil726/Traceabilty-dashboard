import { createContext, useContext } from 'react';

export interface FormFieldContextValue {
  id: string;
  describedBy: string | undefined;
  invalid: boolean;
  required: boolean;
}

export const FormFieldContext = createContext<FormFieldContextValue | null>(null);

/** Controls inside a FormField pick up id, aria-describedby, aria-invalid and required. */
export function useFormField(): FormFieldContextValue | null {
  return useContext(FormFieldContext);
}

