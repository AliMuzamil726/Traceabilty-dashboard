import { Card, KeyValueList, SectionHeader } from '@/design-system/components';
import type { Book, EntryData, FieldDef, FormDefinition } from '../api/types';
import { isEmpty, isVisible, stepTotals, summarise, type LabelOf } from '../lib/schemaLogic';
import { formatAnswer } from '../lib/display';

export interface SubmitSummaryProps {
  book: Book;
  definition: FormDefinition;
  labelOf: LabelOf;
}

function answers(fields: FieldDef[], data: EntryData, labelOf: LabelOf) {
  return fields
    .filter((f) => f.type !== 'photos' && isVisible(f, data) && !isEmpty(data[f.key]))
    .map((f) => ({ label: f.label, value: formatAnswer(f, data[f.key], labelOf) }));
}

/** The whole fieldbook, read only: every step's answers in order. */
export function SubmitSummary({ book, definition, labelOf }: SubmitSummaryProps) {
  const states = new Map(book.steps.map((s) => [s.key, s]));
  return (
    <div className="flex flex-col gap-4">
      {definition.steps.map((step) => {
        const state = states.get(step.key);
        const entries = state?.entries ?? [];
        return (
          <Card key={step.key} padding="md" as="section" aria-labelledby={`sum-${step.key}`}>
            <SectionHeader
              as="h3"
              id={`sum-${step.key}`}
              title={`${step.order}. ${step.title}`}
              description={state?.status === 'not_applicable' ? 'Nothing to record for this step.' : undefined}
            />
            {!step.repeatable && entries[0] && (
              <KeyValueList className="mt-3" columns={2} items={answers(step.fields, entries[0].data, labelOf)} />
            )}
            {step.repeatable && entries.length > 0 && (
              <>
                {(step.totals ?? []).length > 0 && (
                  <p className="mt-2 text-sm text-muted">
                    {stepTotals(step, entries.map((e) => e.data))
                      .map((t) => `${t.label}: ${t.value}`)
                      .join(' · ')}
                  </p>
                )}
                <ol className="mt-3 flex flex-col gap-3">
                  {entries.map((entry) => (
                    <li key={entry.entry_index} className="rounded-md border border-line p-3">
                      <p className="text-sm font-semibold text-ink">
                        Entry {entry.entry_index + 1}: <span className="font-normal">{summarise(step, entry.data, labelOf)}</span>
                      </p>
                      <KeyValueList className="mt-2" columns={2} items={answers(step.fields, entry.data, labelOf)} />
                    </li>
                  ))}
                </ol>
              </>
            )}
            {entries.length === 0 && state?.status !== 'not_applicable' && <p className="mt-2 text-sm text-muted">Not recorded.</p>}
          </Card>
        );
      })}
    </div>
  );
}
