import { ArrowLeft, ArrowRight, CheckCircle2, Send, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { PageContainer } from '@/app/layout/PageContainer';
import { toApiError } from '@/core/api/errors';
import { Badge, Button, Card, ConfirmDialog, EmptyState, PageHeader, Skeleton, toast } from '@/design-system/components';
import { fieldbookApi } from '../api/client';
import type { Book, EntryData, Issue, StepDef } from '../api/types';
import { ActivityTimeline } from '../components/ActivityTimeline';
import { CropClockBar } from '../components/CropClockBar';
import { FarmerSideCard } from '../components/FarmerSideCard';
import { FormStepper } from '../components/FormStepper';
import { PhotoUploader } from '../components/PhotoUploader';
import { RepeatableEntries, type EntrySaveResult } from '../components/RepeatableEntries';
import { SchemaForm } from '../components/SchemaForm';
import { bookPath } from '../lib/display';
import { WarningList } from '../components/WarningList';
import { useBookAction, useFieldbook, useTimeline } from '../hooks/useFieldbook';
import { useFormSchema, useListLabels } from '../hooks/useFormSchema';
import { useStepSave } from '../hooks/useStepSave';
import { useUnsavedGuard } from '../hooks/useUnsavedGuard';
import { initialValues, missingRequired, payloadFor, stepDone } from '../lib/schemaLogic';
import { draftKey, useDraftStore } from '../store/draftStore';

function byField(issues: Issue[], stepKey: string, index = 0): Record<string, string> {
  return Object.fromEntries(
    issues.filter((i) => i.step_key === stepKey && i.entry_index === index).map((i) => [i.field, i.message]),
  );
}

export default function FieldbookEditorPage() {
  const { bookId = '' } = useParams();
  const book = useFieldbook(bookId);
  const schema = useFormSchema(book.data?.crop);

  if (book.error) {
    const err = toApiError(book.error);
    return (
      <PageContainer>
        <EmptyState
          title={err.status === 404 ? 'Fieldbook not found' : 'This fieldbook cannot be opened'}
          description={err.message}
        />
      </PageContainer>
    );
  }
  if (!book.data || !schema.data) {
    return (
      <PageContainer>
        <div className="flex flex-col gap-4">
          <Skeleton className="h-10 w-72" />
          <Skeleton className="h-96 w-full" />
        </div>
      </PageContainer>
    );
  }
  if (book.data.locked) return <Navigate to={bookPath(book.data.id, true)} replace />;
  return (
    <PageContainer>
      <Editor book={book.data} steps={schema.data.steps} country={schema.data.country} />
    </PageContainer>
  );
}

function Editor({ book, steps, country }: { book: Book; steps: StepDef[]; country: string }) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const definition = useFormSchema(book.crop).data;
  const labelOf = useListLabels(definition);
  const timeline = useTimeline(book.id, book.version);
  const { save, saving } = useStepSave(book);

  const drafts = useDraftStore((s) => s.drafts);
  const setDraft = useDraftStore((s) => s.setDraft);
  const clearDraft = useDraftStore((s) => s.clearDraft);
  const clearBook = useDraftStore((s) => s.clearBook);
  const dirty = Object.keys(drafts).some((k) => k.startsWith(`${book.id}:`));
  const blocker = useUnsavedGuard(dirty);

  const requested = params.get('step');
  const currentKey = steps.some((s) => s.key === requested) ? (requested as string) : (book.current_step ?? steps[0]!.key);
  const index = steps.findIndex((s) => s.key === currentKey);
  const step = steps[index]!;
  const isLast = index === steps.length - 1;
  const state = book.steps.find((s) => s.key === step.key);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [warnings, setWarnings] = useState<Record<string, string>>({});
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    setErrors({});
    setWarnings(byField(book.warnings, step.key));
    // Only when the step changes; later warnings come from saves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step.key]);

  const go = (key: string) => {
    setParams({ step: key }, { replace: true });
    window.scrollTo({ top: 0 });
  };

  const singleKey = draftKey(book.id, step.key);
  const singleValues: EntryData = drafts[singleKey] ?? initialValues(step, book.defaults, state?.entries[0]);
  const notApplicable = state?.status === 'not_applicable';

  const photos = useBookAction(book.id, (files: File[]) => fieldbookApi.addPhotos(book, files));
  const removePhoto = useBookAction(book.id, (photoId: string) => fieldbookApi.deletePhoto(book, photoId));
  const deleteEntry = useBookAction(book.id, (i: number) => fieldbookApi.deleteEntry(book, step.key, i));
  const markNa = useBookAction(book.id, (value: boolean) => fieldbookApi.setNotApplicable(book, step.key, value));
  const submit = useBookAction(book.id, () => fieldbookApi.submit(book));

  const photoSlot = (
    <PhotoUploader
      photos={book.photos}
      uploading={photos.isPending}
      onUpload={(files) => photos.mutate(files)}
      onRemove={(id) => removePhoto.mutate(id)}
    />
  );

  /** Save the open single step. Returns false when the officer must fix something first. */
  const saveSingle = async (): Promise<boolean> => {
    if (step.repeatable || notApplicable) return true;
    const missing = missingRequired(step, singleValues);
    if (missing.length) {
      setErrors(Object.fromEntries(missing.map((k) => [k, 'Answer this question.'])));
      return false;
    }
    const outcome = await save({ stepKey: step.key, data: payloadFor(step, singleValues) });
    setErrors(outcome.fieldErrors);
    if (!outcome.ok) {
      if (outcome.message && !Object.keys(outcome.fieldErrors).length) toast.error('Not saved', outcome.message);
      return false;
    }
    clearDraft(singleKey);
    const stepWarnings = Object.fromEntries(outcome.warnings.map((w) => [w.field, w.message]));
    setWarnings(stepWarnings);
    if (outcome.warnings.length) toast.warning('Saved with warnings', 'Check the highlighted answers.');
    return true;
  };

  const saveEntry = async (which: number | 'new', data: EntryData): Promise<EntrySaveResult> => {
    const outcome = await save({ stepKey: step.key, data, entry: which });
    if (!outcome.ok && outcome.message && !Object.keys(outcome.fieldErrors).length) toast.error('Not saved', outcome.message);
    if (outcome.ok) toast.success('Entry saved');
    return {
      ok: outcome.ok,
      fieldErrors: outcome.fieldErrors,
      warnings: Object.fromEntries(outcome.warnings.map((w) => [w.field, w.message])),
    };
  };

  const unsavedEntries = step.repeatable && Object.keys(drafts).some((k) => k.startsWith(`${book.id}:${step.key}:`));

  const next = async () => {
    if (unsavedEntries) {
      toast.warning('Save or discard the open entry first');
      return;
    }
    if (!(await saveSingle())) return;
    if (isLast) setConfirmSubmit(true);
    else go(steps[index + 1]!.key);
  };

  const errorSteps = useMemo(() => new Set(book.errors.map((e) => e.step_key)), [book.errors]);
  const titles = new Map(steps.map((s) => [s.key, s.title]));
  const isComplete = stepDone(state);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={`${book.crop === 'cotton' ? 'Cotton' : 'Hemp'} fieldbook ${book.season_year}`}
        subtitle={`${book.farmer.name}, field ${book.field.field_id}. Draft, saved step by step.`}
        breadcrumb={[{ label: 'Fieldbook', to: '/fieldbook' }, { label: book.field.field_id }]}
        actions={
          <Button variant="ghost" size="sm" leftIcon={<Trash2 className="h-4 w-4" />} onClick={() => setConfirmDelete(true)}>
            Delete draft
          </Button>
        }
      />

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[248px_minmax(0,1fr)_310px]">
        <aside className="rounded-card border border-line bg-surface p-3.5 shadow-1 lg:sticky lg:top-20">
          <FormStepper steps={steps} states={book.steps} current={step.key} onSelect={go} errorSteps={errorSteps} />
        </aside>

        <Card padding="lg" as="section" aria-labelledby="step-title" className="flex flex-col overflow-hidden">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-pill bg-forest-50 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-forest-800">
                  Step {index + 1} of {steps.length}
                </span>
                {step.repeatable && (
                  <Badge tone="neutral" size="sm">
                    Multiple entries allowed
                  </Badge>
                )}
                {isComplete && (
                  <Badge tone="success" size="sm">
                    <CheckCircle2 className="mr-1 inline h-3 w-3" aria-hidden />
                    Saved
                  </Badge>
                )}
              </div>
              <h2 id="step-title" className="mt-2 text-xl font-semibold text-ink">
                {step.title}
              </h2>
            </div>

            {step.allow_not_applicable && (
              <label className="flex cursor-pointer items-center gap-2.5 rounded-control border border-line bg-canvas px-3.5 py-2 text-sm font-medium text-ink transition-colors hover:bg-forest-50/50">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-forest-700"
                  checked={notApplicable}
                  disabled={markNa.isPending || (state?.entry_count ?? 0) > 0}
                  onChange={(e) => markNa.mutate(e.target.checked)}
                />
                <span>Nothing to record for this step</span>
                {(state?.entry_count ?? 0) > 0 && (
                  <span className="text-xs font-normal text-muted">(delete the entries first)</span>
                )}
              </label>
            )}
          </div>

          <div className="mt-6">
            {notApplicable ? (
              <div className="rounded-card border border-line bg-canvas px-5 py-8 text-center">
                <p className="text-sm font-medium text-ink">Marked as nothing to record for this step.</p>
                <p className="mt-1 text-xs text-muted">Untick the checkbox above if you need to add entries.</p>
              </div>
            ) : step.repeatable ? (
              <RepeatableEntries
                key={step.key}
                bookId={book.id}
                step={step}
                entries={state?.entries ?? []}
                defaults={book.defaults}
                country={country}
                crop={book.crop}
                labelOf={labelOf}
                saving={saving}
                onSave={saveEntry}
                onDelete={(i) => deleteEntry.mutate(i)}
                photos={photoSlot}
              />
            ) : (
              <SchemaForm
                key={step.key}
                step={step}
                values={singleValues}
                onChange={(v) => setDraft(singleKey, v)}
                country={country}
                crop={book.crop}
                errors={errors}
                warnings={warnings}
                photos={photoSlot}
              />
            )}
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
            <Button
              variant="secondary"
              leftIcon={<ArrowLeft className="h-4 w-4" />}
              disabled={index === 0}
              onClick={() => go(steps[index - 1]!.key)}
            >
              Back
            </Button>
            <div className="flex items-center gap-3">
              {dirty && !step.repeatable && (
                <span className="text-xs font-medium text-wheat-600">Unsaved changes</span>
              )}
              <Button
                loading={saving}
                rightIcon={isLast ? <Send className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
                onClick={() => void next()}
              >
                {isLast ? 'Save and Submit' : 'Save and Next'}
              </Button>
            </div>
          </div>
        </Card>

        <aside className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:col-span-2 xl:col-span-1 xl:grid-cols-1">
          <FarmerSideCard book={book} />
          <CropClockBar clock={book.crop_clock} status={book.crop_status} />
          <div className="md:col-span-2 xl:col-span-1">
            <ActivityTimeline items={timeline.data?.items} loading={timeline.isLoading} />
          </div>
        </aside>
      </div>

      <ConfirmDialog
        open={confirmSubmit}
        title="Submit this fieldbook?"
        confirmLabel="Submit and lock"
        loading={submit.isPending}
        onCancel={() => setConfirmSubmit(false)}
        onConfirm={() =>
          submit.mutate(undefined, {
            onSuccess: (done) => {
              setConfirmSubmit(false);
              clearBook(book.id);
              toast.success('Fieldbook submitted', 'It is now locked and read only.');
              navigate(bookPath(done.id, true));
            },
            onError: () => setConfirmSubmit(false),
          })
        }
        description={
          <div className="flex flex-col gap-3">
            <p>Once submitted, the fieldbook is locked permanently. Nobody can change it afterwards.</p>
            {book.missing_steps.length > 0 && (
              <p className="text-danger">
                Still to complete: {book.missing_steps.map((k) => titles.get(k) ?? k).join(', ')}.
              </p>
            )}
            {(book.errors.length > 0 || book.warnings.length > 0) && (
              <div>
                <p className="mb-2 font-medium text-ink">
                  {book.errors.length > 0 ? 'Fix these first' : 'Please check these answers'}
                </p>
                <WarningList
                  issues={[...book.errors, ...book.warnings]}
                  steps={steps}
                  onGo={(key) => {
                    setConfirmSubmit(false);
                    go(key);
                  }}
                />
              </div>
            )}
          </div>
        }
      />

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this draft fieldbook?"
        description="Every entry and photo in this draft is removed. Only the officer who started it, or an administrator, can do this."
        confirmLabel="Delete draft"
        destructive
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => {
          setConfirmDelete(false);
          fieldbookApi
            .remove(book.id)
            .then(() => {
              clearBook(book.id);
              toast.success('Draft deleted');
              navigate('/fieldbook', { replace: true });
            })
            .catch((e: unknown) => toast.error('The draft was not deleted', toApiError(e).message));
        }}
      />

      <ConfirmDialog
        open={blocker.state === 'blocked'}
        title="Leave without saving?"
        description="Answers you have typed but not saved will be lost."
        confirmLabel="Leave"
        cancelLabel="Stay"
        destructive
        onCancel={() => blocker.reset?.()}
        onConfirm={() => {
          clearBook(book.id);
          blocker.proceed?.();
        }}
      />
    </div>
  );
}
