import { Lock } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { PageContainer } from '@/app/layout/PageContainer';
import { toApiError } from '@/core/api/errors';
import { formatDateTime } from '@/core/utils/format';
import { Badge, Card, EmptyState, PageHeader, SectionHeader, Skeleton, buttonClasses } from '@/design-system/components';
import { ActivityTimeline } from '../components/ActivityTimeline';
import { CropClockBar } from '../components/CropClockBar';
import { FarmerSideCard } from '../components/FarmerSideCard';
import { PhotoUploader } from '../components/PhotoUploader';
import { SubmitSummary } from '../components/SubmitSummary';
import { useFieldbook, useTimeline } from '../hooks/useFieldbook';
import { useFormSchema, useListLabels } from '../hooks/useFormSchema';

/** The read-only fieldbook. A draft opened here links back to the editor. */
export default function FieldbookViewPage() {
  const { bookId = '' } = useParams();
  const book = useFieldbook(bookId);
  const schema = useFormSchema(book.data?.crop);
  const labelOf = useListLabels(schema.data);
  const timeline = useTimeline(bookId, book.data?.version);

  if (book.error) {
    return (
      <PageContainer>
        <EmptyState title="This fieldbook cannot be opened" description={toApiError(book.error).message} />
      </PageContainer>
    );
  }
  if (!book.data || !schema.data) {
    return (
      <PageContainer>
        <Skeleton className="h-96 w-full" />
      </PageContainer>
    );
  }
  const b = book.data;

  return (
    <PageContainer>
      <div className="flex flex-col gap-6">
        <PageHeader
          title={`${b.crop === 'cotton' ? 'Cotton' : 'Hemp'} fieldbook ${b.season_year}`}
          subtitle={`${b.farmer.name}, field ${b.field.field_id}`}
          breadcrumb={[{ label: 'Fieldbook', to: '/fieldbook' }, { label: b.field.field_id }]}
          actions={
            b.locked ? (
              <Badge tone="success" dot>
                <Lock className="mr-1 inline h-3.5 w-3.5" aria-hidden />
                Submitted {formatDateTime(b.submitted_at)}
              </Badge>
            ) : (
              <Link to={`/fieldbook/books/${b.id}`} className={buttonClasses('primary', 'sm')}>
                Continue editing
              </Link>
            )
          }
        />
        {b.locked && (
          <p className="rounded-md border border-forest-100 bg-forest-50 px-4 py-3 text-sm text-forest-900" role="status">
            This fieldbook is submitted and locked. It is read only.
          </p>
        )}
        <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_310px]">
          <div className="flex flex-col gap-4">
            <SubmitSummary book={b} definition={schema.data} labelOf={labelOf} />
            <Card padding="md" as="section" aria-labelledby="photos-title">
              <SectionHeader as="h3" id="photos-title" title="Photos" />
              <div className="mt-3">
                <PhotoUploader photos={b.photos} readOnly onUpload={() => undefined} onRemove={() => undefined} />
              </div>
            </Card>
          </div>
          <aside className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-1">
            <FarmerSideCard book={b} />
            <CropClockBar clock={b.crop_clock} status={b.crop_status} />
            <div className="md:col-span-2 xl:col-span-1">
              <ActivityTimeline items={timeline.data?.items} loading={timeline.isLoading} limit={30} />
            </div>
          </aside>
        </div>
      </div>
    </PageContainer>
  );
}
