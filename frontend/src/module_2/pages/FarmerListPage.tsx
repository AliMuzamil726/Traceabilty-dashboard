import { useQuery } from '@tanstack/react-query';
import { MapPinPlus, Search, UserPlus, Users } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { PageContainer } from '@/app/layout/PageContainer';
import { toApiError } from '@/core/api/errors';
import { useMasterList } from '@/core/hooks/useSharedData';
import { formatDate } from '@/core/utils/format';
import { Badge, StatusPill } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { DataTable, type Column } from '@/design-system/components/DataTable';
import { EmptyState } from '@/design-system/components/EmptyState';
import { ErrorState } from '@/design-system/components/ErrorState';
import { Input } from '@/design-system/components/Input';
import { PageHeader } from '@/design-system/components/PageHeader';
import { Select } from '@/design-system/components/Select';
import { buttonClasses } from '@/design-system/components/buttonStyles';
import { registerApi, registerKeys } from '../api/client';
import type { Crop, FarmerListItem } from '../api/types';
import { CROP_LABEL } from '../format';
import { useFieldOffices } from '../hooks/useFieldOffices';

const PAGE_SIZE = 25;

export default function FarmerListPage() {
  const navigate = useNavigate();
  // A link (from the Home, say) may open the list narrowed to one crop.
  const [address] = useSearchParams();
  const linkedCrop = address.get('crop');
  const [q, setQ] = useState(address.get('q') ?? '');
  const [crop, setCrop] = useState<Crop | ''>(
    linkedCrop === 'cotton' || linkedCrop === 'hemp' ? linkedCrop : '',
  );
  const [officeId, setOfficeId] = useState('');
  const [page, setPage] = useState(1);

  const crops = useMasterList('crop');
  // Offices for the chosen crop's country; with no crop chosen, both countries' lists
  // are irrelevant, so the filter only appears once a crop narrows it.
  const offices = useFieldOffices(crop === 'hemp' ? 'GB' : 'PK');

  const params = {
    q: q.trim() || undefined,
    crop: crop || undefined,
    field_office_id: officeId || undefined,
    page,
    page_size: PAGE_SIZE,
  };

  const farmers = useQuery({
    queryKey: registerKeys.farmers(params),
    queryFn: ({ signal }) => registerApi.listFarmers(params, signal),
  });

  const columns: Column<FarmerListItem>[] = [
    {
      key: 'sawie_id',
      header: 'SAWIE ID',
      mono: true,
      width: '110px',
      cell: (farmer) => (
        <Link to={`/register/farmers/${farmer.id}`} className="font-medium hover:underline">
          {farmer.sawie_id}
        </Link>
      ),
    },
    {
      key: 'name',
      header: 'Name',
      width: '180px',
      cell: (farmer) => (
        <span className="flex flex-col">
          <span className="font-medium text-ink">{farmer.name}</span>
          <span className="text-sm text-muted">
            {farmer.crop === 'cotton' ? farmer.father_name : farmer.farm_name}
          </span>
        </span>
      ),
    },
    {
      key: 'crop',
      header: 'Crop',
      cell: (farmer) => (
        <Badge tone={farmer.crop === 'cotton' ? 'success' : 'accent'}>
          {CROP_LABEL[farmer.crop]}
        </Badge>
      ),
    },
    {
      key: 'id_number',
      header: 'ID number',
      mono: true,
      cell: (farmer) => farmer.id_number_masked,
    },
    { key: 'phone', header: 'Phone', mono: true, cell: (farmer) => farmer.phone_masked ?? '-' },
    { key: 'location', header: 'Location', width: '240px', cell: (farmer) => farmer.location_summary },
    {
      key: 'officer',
      header: 'Field officer',
      width: '160px',
      cell: (farmer) => farmer.registered_by?.full_name ?? '—',
    },
    {
      key: 'fields',
      header: 'Fields',
      nowrap: true,
      cell: (farmer) =>
        farmer.has_fields ? (
          <StatusPill tone="success">
            {farmer.field_count} field{farmer.field_count === 1 ? '' : 's'} mapped
          </StatusPill>
        ) : (
          <StatusPill tone="warning">No field yet</StatusPill>
        ),
    },
    {
      key: 'created_at',
      header: 'Registered',
      nowrap: true,
      cell: (farmer) => formatDate(farmer.created_at),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      nowrap: true,
      cell: (farmer) => (
        <span className="flex items-center justify-end gap-1.5">
          <Link
            to={`/register/farmers/${farmer.id}/fields/new`}
            onClick={(event) => event.stopPropagation()}
            className={buttonClasses(farmer.has_fields ? 'secondary' : 'primary', 'sm')}
          >
            <MapPinPlus className="h-3.5 w-3.5" aria-hidden />
            <span>Add field</span>
          </Link>
          <Link
            to={`/register/farmers/${farmer.id}`}
            onClick={(event) => event.stopPropagation()}
            className={buttonClasses('ghost', 'sm')}
          >
            Open
          </Link>
        </span>
      ),
    },
  ];

  const total = farmers.data?.total ?? 0;
  const unfiltered = !q.trim() && !crop && !officeId;

  return (
    <PageContainer>
      <PageHeader
        title="Register Farmer"
        subtitle="Register farmers under a crop programme and map their fields."
        breadcrumb={[{ label: 'Home', to: '/' }, { label: 'Register Farmer' }]}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Link to="/register/add-field" className={buttonClasses('secondary', 'md')}>
              <MapPinPlus className="h-4 w-4" aria-hidden />
              <span>Add field</span>
            </Link>
            <Link to="/register/new" className={buttonClasses('primary', 'md')}>
              <UserPlus className="h-4 w-4" aria-hidden />
              <span>Register farmer</span>
            </Link>
          </div>
        }
      />

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <Input
            id="farmer-search"
            aria-label="Search by SAWIE ID, CNIC / ID number, phone, or name"
            type="search"
            placeholder="SAWIE ID, name, CNIC / ID number or phone"
            leadingIcon={<Search />}
            value={q}
            onChange={(event) => {
              setQ(event.target.value);
              setPage(1);
            }}
          />
        </div>

        <div className="w-40">
          <Select
            id="crop-filter"
            aria-label="Crop"
            placeholder="Every crop"
            value={crop}
            options={(crops.data?.items ?? []).map((item) => ({
              value: item.value,
              label: item.label,
            }))}
            onChange={(event) => {
              setCrop(event.target.value as Crop | '');
              setOfficeId('');
              setPage(1);
            }}
          />
        </div>

        {crop && (
          <div className="w-56">
            <Select
              id="office-filter"
              aria-label="Field office"
              placeholder="Every office"
              value={officeId}
              options={(offices.data ?? []).map((office) => ({
                value: office.id,
                label: office.name,
              }))}
              onChange={(event) => {
                setOfficeId(event.target.value);
                setPage(1);
              }}
            />
          </div>
        )}
      </div>

      <div className="mt-5">
        <DataTable
          caption="Farmers registered by you, with their ID numbers masked"
          columns={columns}
          rows={farmers.data?.items ?? []}
          rowKey={(farmer) => farmer.id}
          loading={farmers.isLoading}
          onRowClick={(farmer) => navigate(`/register/farmers/${farmer.id}`)}
          pagination={{
            page,
            pageSize: PAGE_SIZE,
            total,
            onPageChange: setPage,
          }}
          empty={
            farmers.isError ? (
              <ErrorState
                title="Farmers could not be loaded"
                description={toApiError(farmers.error).message}
                onRetry={() => void farmers.refetch()}
              />
            ) : unfiltered ? (
              <EmptyState
                icon={<Users />}
                title="No farmers registered yet"
                description="Register the first farmer, then map their fields so they can be traced through to a bale."
                action={
                  <Link to="/register/new" className={buttonClasses('primary', 'md')}>
                    <UserPlus className="h-4 w-4" aria-hidden />
                    <span>Register farmer</span>
                  </Link>
                }
              />
            ) : (
              <EmptyState
                icon={<Search />}
                title="No farmers match this search"
                description="Check the SAWIE ID or spelling, or clear the filters."
                action={
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setQ('');
                      setCrop('');
                      setOfficeId('');
                      setPage(1);
                    }}
                  >
                    Clear filters
                  </Button>
                }
              />
            )
          }
        />
      </div>
    </PageContainer>
  );
}
