import { Plus } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Button, ConfirmDialog, EmptyState } from '@/design-system/components';
import type { Entry, EntryData, StepDef } from '../api/types';
import { initialValues, payloadFor, stepTotals, summarise, type LabelOf } from '../lib/schemaLogic';
import { draftKey, useDraftStore } from '../store/draftStore';
import { EntryAccordion } from './EntryAccordion';
import { SchemaForm } from './SchemaForm';

export interface EntrySaveResult {
  ok: boolean;
  fieldErrors: Record<string, string>;
  warnings: Record<string, string>;
}

export interface RepeatableEntriesProps {
  bookId: string;
  step: StepDef;
  entries: Entry[];
  defaults: Record<string, unknown>;
  country: string;
  crop: string;
  labelOf: LabelOf;
  readOnly?: boolean;
  saving?: boolean;
  onSave: (entry: number | 'new', data: EntryData) => Promise<EntrySaveResult>;
  onDelete: (index: number) => Promise<void> | void;
  photos?: ReactNode;
}

/**
 * The entries of a repeatable step (irrigations, pickings, sprays). Each is an accordion
 * with its own save; new and duplicated entries are drafts until saved.
 */
export function RepeatableEntries(props: RepeatableEntriesProps) {
  const { bookId, step, entries, defaults, country, crop, labelOf, readOnly, saving, onSave, onDelete, photos } = props;
  const drafts = useDraftStore((s) => s.drafts);
  const setDraft = useDraftStore((s) => s.setDraft);
  const clearDraft = useDraftStore((s) => s.clearDraft);
  const [open, setOpen] = useState<number | 'new' | null>(entries.length === 0 && !readOnly ? 'new' : null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [warnings, setWarnings] = useState<Record<string, string>>({});
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const newKey = draftKey(bookId, step.key, 'new');
  const hasNew = Boolean(drafts[newKey]) || (open === 'new' && !readOnly);
  const valuesFor = (which: number | 'new'): EntryData => {
    const key = draftKey(bookId, step.key, which);
    if (drafts[key]) return drafts[key];
    if (which === 'new') return initialValues(step, defaults);
    return initialValues(step, defaults, entries.find((e) => e.entry_index === which));
  };

  const toggle = (which: number | 'new') => {
    setErrors({});
    setWarnings({});
    setOpen(open === which ? null : which);
  };

  const save = async (which: number | 'new') => {
    const result = await onSave(which, payloadFor(step, valuesFor(which)));
    setErrors(result.fieldErrors);
    setWarnings(result.warnings);
    if (result.ok) {
      clearDraft(draftKey(bookId, step.key, which));
      if (Object.keys(result.warnings).length === 0) setOpen(null);
    }
  };

  const duplicate = (index: number) => {
    const source = valuesFor(index);
    setDraft(newKey, { ...source });
    setErrors({});
    setOpen('new');
  };

  const totals = stepTotals(step, entries.map((e) => e.data));
  const noun = step.title.toLowerCase();

  const form = (which: number | 'new') => (
    <SchemaForm
      step={step}
      values={valuesFor(which)}
      onChange={(v) => setDraft(draftKey(bookId, step.key, which), v)}
      country={country}
      crop={crop}
      errors={open === which ? errors : {}}
      warnings={open === which ? warnings : {}}
      readOnly={readOnly}
      photos={photos}
    />
  );

  return (
    <div className="flex flex-col gap-3">
      {entries.length > 0 && totals.length > 0 && (
        <p className="text-sm text-muted" data-testid="step-totals">
          {totals.map((t, i) => (
            <span key={t.label}>
              {i > 0 && <span aria-hidden> · </span>}
              {t.label}: <span className="font-medium text-ink tabular">{t.value}</span>
            </span>
          ))}
        </p>
      )}

      {entries.length === 0 && !hasNew && (
        <EmptyState compact title={`No ${noun} recorded yet`} description={readOnly ? undefined : 'Add the first entry to start this step.'} />
      )}

      {entries.map((entry) => (
        <EntryAccordion
          key={entry.entry_index}
          title={`Entry ${entry.entry_index + 1}`}
          summary={summarise(step, entry.data, labelOf)}
          open={open === entry.entry_index}
          onToggle={() => toggle(entry.entry_index)}
          unsaved={Boolean(drafts[draftKey(bookId, step.key, entry.entry_index)])}
          onDuplicate={readOnly ? undefined : () => duplicate(entry.entry_index)}
          onDelete={readOnly ? undefined : () => setConfirmDelete(entry.entry_index)}
          footer={
            readOnly ? null : (
              <Button type="button" size="sm" loading={saving} onClick={() => void save(entry.entry_index)}>
                Save entry
              </Button>
            )
          }
        >
          {form(entry.entry_index)}
        </EntryAccordion>
      ))}

      {!readOnly && hasNew && (
        <EntryAccordion
          title={`Entry ${entries.length + 1}`}
          summary="New entry"
          open={open === 'new'}
          onToggle={() => toggle('new')}
          unsaved
          onDelete={() => {
            clearDraft(newKey);
            setOpen(null);
          }}
          footer={
            <Button type="button" size="sm" loading={saving} onClick={() => void save('new')}>
              Save entry
            </Button>
          }
        >
          {form('new')}
        </EntryAccordion>
      )}

      {!readOnly && !hasNew && (
        <Button
          type="button"
          variant="secondary"
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => {
            setErrors({});
            setOpen('new');
          }}
          className="self-start"
        >
          Add entry
        </Button>
      )}

      <ConfirmDialog
        open={confirmDelete !== null}
        title="Delete this entry?"
        description="The entry is removed from the fieldbook. This cannot be undone."
        confirmLabel="Delete entry"
        destructive
        onCancel={() => setConfirmDelete(null)}
        onConfirm={() => {
          const index = confirmDelete;
          setConfirmDelete(null);
          if (index !== null) {
            clearDraft(draftKey(bookId, step.key, index));
            void onDelete(index);
          }
        }}
      />
    </div>
  );
}
