import { AnimatePresence, motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '@/core/utils/cn';
import { transition } from '@/design-system/motion';
import type { EntryData, StepDef } from '../api/types';
import { isVisible, suggestionFor, withComputed } from '../lib/schemaLogic';
import { FieldRenderer } from './FieldRenderer';

export interface SchemaFormProps {
  step: StepDef;
  values: EntryData;
  onChange: (values: EntryData) => void;
  country: string;
  crop: string;
  /** Messages keyed by field, or "field.part" for paired numbers. */
  errors?: Record<string, string>;
  warnings?: Record<string, string>;
  readOnly?: boolean;
  photos?: ReactNode;
}

/**
 * Renders one step's fields from its definition. Nothing about a step is written here:
 * labels, types, units, lists and conditions all come from the schema.
 *
 * Layout: responsive 1→2 column grid. Each field sits in a light card. Cards use
 * min-w-0 so flex/grid children (especially number + unit) never collapse.
 */
export function SchemaForm({
  step,
  values,
  onChange,
  country,
  crop,
  errors = {},
  warnings = {},
  readOnly,
  photos,
}: SchemaFormProps) {
  const set = (key: string, value: unknown) => onChange(withComputed(step, { ...values, [key]: value }));

  return (
    <div className="grid grid-cols-1 items-start gap-x-6 gap-y-5 sm:grid-cols-2">
      <AnimatePresence initial={false}>
        {step.fields
          .filter((f) => isVisible(f, values))
          .map((field) => {
            const wide = ['multiselect', 'paired_number', 'photos', 'dates', 'yesno'].includes(field.type);
            const partErrors = Object.fromEntries(
              Object.entries(errors)
                .filter(([k]) => k.startsWith(`${field.key}.`))
                .map(([k, v]) => [k.slice(field.key.length + 1).replace(/^\d+\./, ''), v]),
            );
            return (
              <motion.div
                key={field.key}
                layout="position"
                initial={field.visible_if ? { opacity: 0, height: 0 } : false}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={transition('base')}
                className={cn(
                  // min-w-0 is critical: without it, grid children refuse to shrink and
                  // number+unit rows collapse the input to a few pixels.
                  'min-w-0 rounded-control border border-line/70 bg-canvas/45 p-3.5 transition-colors focus-within:border-forest-500/60 focus-within:bg-surface',
                  wide && 'sm:col-span-2',
                )}
                data-field={field.key}
              >
                <FieldRenderer
                  field={field}
                  value={values[field.key]}
                  onChange={(v) => set(field.key, v)}
                  country={country}
                  crop={crop}
                  error={errors[field.key]}
                  partErrors={Object.keys(partErrors).length ? partErrors : undefined}
                  warning={warnings[field.key]}
                  suggestion={readOnly ? undefined : suggestionFor(step, field, values)}
                  readOnly={readOnly}
                  photos={photos}
                />
              </motion.div>
            );
          })}
      </AnimatePresence>
    </div>
  );
}
