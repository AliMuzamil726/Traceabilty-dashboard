import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, MapPinPlus, Pencil, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { PageContainer } from '@/app/layout/PageContainer';
import { ApiError } from '@/core/api/errors';
import { formatDate, formatDecimal } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { DataTable, type Column } from '@/design-system/components/DataTable';
import { PageHeader } from '@/design-system/components/PageHeader';
import { Skeleton } from '@/design-system/components/Skeleton';
import { StatCard } from '@/design-system/components/StatCard';
import { buttonClasses } from '@/design-system/components/buttonStyles';
import { toast } from '@/design-system/components/toastStore';
import { registerApi, registerKeys } from '../api/client';
import type { Field, SeasonProfile } from '../api/types';
import { FarmerSummaryCard } from '../components/FarmerSummaryCard';
import { FieldTable } from '../components/FieldTable';
import { VertexDrawer } from '../components/VertexDrawer';

export default function FarmerProfilePage() {
  const { farmerId = '' } = useParams<{ farmerId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [vertexField, setVertexField] = useState<Field | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);

  const profile = useQuery({
    queryKey: registerKeys.profile(farmerId),
    queryFn: ({ signal }) => registerApi.getFarmerProfile(farmerId, signal),
    enabled: Boolean(farmerId),
  });

  const remove = useMutation({
    mutationFn: (field: Field) => registerApi.deleteField(field.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: registerKeys.all });
      toast.success('Field removed', 'Its field ID will not be reused.');
    },
    onError: (error) =>
      toast.error(
        'Could not remove the field',
        error instanceof ApiError ? error.message : undefined,
      ),
  });

  if (profile.isLoading) {
    return (
      <PageContainer>
        <Skeleton className="h-8 w-64" shape="block" />
        <Skeleton className="mt-6 h-40" shape="block" />
        <Skeleton className="mt-4 h-64" shape="block" />
      </PageContainer>
    );
  }

  if (profile.isError || !profile.data) {
    return (
      <PageContainer>
        <PageHeader title="Farmer not found" subtitle="This farmer does not exist, or was removed." />
        <Link to="/register" className={`${buttonClasses('secondary', 'md')} mt-6`}>
          Back to farmers
        </Link>
      </PageContainer>
    );
  }

  const { farmer, season_profiles: seasons, fields, completeness } = profile.data;

  const seasonColumns: Column<SeasonProfile>[] = [
    { key: 'season_year', header: 'Season', numeric: true, cell: (row) => row.season_year },
    { key: 'variety', header: 'Variety', cell: (row) => row.variety },
    { key: 'tenure', header: 'Tenure', cell: (row) => row.tenure },
    { key: 'previous_crop', header: 'Previous crop', cell: (row) => row.previous_crop ?? '-' },
    { key: 'updated_at', header: 'Updated', cell: (row) => formatDate(row.updated_at) },
  ];

  return (
    <PageContainer>
      <PageHeader
        title={farmer.name}
        subtitle={
          farmer.registered_by?.full_name
            ? `Registered by ${farmer.registered_by.full_name} on ${formatDate(farmer.created_at)}`
            : `Registered on ${formatDate(farmer.created_at)}`
        }
        breadcrumb={[
          { label: 'Register Farmer', to: '/register' },
          { label: `SAWIE ID ${farmer.sawie_id}` },
        ]}
        actions={
          <span className="flex flex-wrap items-center gap-2">
            <Link
              to={`/register/farmers/${farmer.id}/edit`}
              className={buttonClasses('secondary', 'md')}
            >
              <Pencil className="h-4 w-4" aria-hidden />
              <span>Edit farmer</span>
            </Link>
            <Link
              to={`/register/farmers/${farmer.id}/fields/new`}
              className={buttonClasses('primary', 'md')}
            >
              <MapPinPlus className="h-4 w-4" aria-hidden />
              <span>Add field</span>
            </Link>
          </span>
        }
      />

      {/* A farmer without a field cannot be carried into the Fieldbook, so say so here
          rather than letting the next module refuse them. */}
      {!completeness.ready_for_fieldbook && (
        <Card padding="md" className="mt-6 border-wheat-300/70 bg-wheat-50">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="flex items-start gap-3">
              <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-wheat-600" aria-hidden />
              <span>
                <span className="block font-medium text-ink">This farmer is not complete yet</span>
                <span className="mt-0.5 block text-base text-muted">
                  {completeness.missing.join(', ')}. A farmer is only ready for the fieldbook once
                  at least one field is mapped.
                </span>
              </span>
            </span>
            <Link
              to={`/register/farmers/${farmer.id}/fields/new`}
              className={buttonClasses('primary', 'md')}
            >
              <MapPinPlus className="h-4 w-4" aria-hidden />
              <span>Map a field</span>
            </Link>
          </div>
        </Card>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Fields mapped" value={completeness.field_count} />
        <StatCard
          label="Total area"
          value={
            farmer.crop === 'cotton'
              ? `${formatDecimal(completeness.total_area_acre, 2)} acres`
              : `${formatDecimal(completeness.total_area_ha, 2)} ha`
          }
        />
        <StatCard label="Seasons recorded" value={seasons.length} />
        <StatCard
          label="Ready for fieldbook"
          value={
            completeness.ready_for_fieldbook ? (
              <Badge tone="success">Yes</Badge>
            ) : (
              <Badge tone="warning">Not yet</Badge>
            )
          }
        />
      </div>

      <div className="mt-6 flex flex-col gap-5">
        <FarmerSummaryCard farmer={farmer} season={seasons[0] ?? null} />

        <section>
          <SectionHeader
            title="Fields"
            description="Boundaries mapped for this farmer."
            className="mb-3"
          />
          <FieldTable
            fields={fields}
            selectedFieldId={selectedFieldId}
            deleting={remove.isPending}
            onSelect={setSelectedFieldId}
            onLocate={(field) =>
              navigate(`/register/farmers/${farmer.id}/fields/${field.id}/edit`)
            }
            onEdit={(field) => navigate(`/register/farmers/${farmer.id}/fields/${field.id}/edit`)}
            onDelete={(field) => remove.mutate(field)}
            onShowVertices={setVertexField}
          />
        </section>

        <section>
          <SectionHeader
            title="Seasons"
            description="Crop details are recorded per season, so a farmer returns without a duplicate record."
            className="mb-3"
          />
          <DataTable
            caption="Season profiles for this farmer"
            columns={seasonColumns}
            rows={seasons}
            rowKey={(row) => String(row.season_year)}
            empty={<p className="px-4 py-10 text-center text-muted">No seasons recorded yet.</p>}
          />
        </section>

        {completeness.ready_for_fieldbook && (
          <div className="flex justify-end">
            <Button
              rightIcon={<ArrowRight className="h-4 w-4" />}
              onClick={() => navigate(`/fieldbook?farmerId=${farmer.id}`)}
            >
              Open the fieldbook
            </Button>
          </div>
        )}
      </div>

      <VertexDrawer
        field={vertexField}
        open={vertexField !== null}
        onClose={() => setVertexField(null)}
      />
    </PageContainer>
  );
}
