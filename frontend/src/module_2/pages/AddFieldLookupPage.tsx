import { useQuery } from '@tanstack/react-query';
import { ArrowRight, MapPinPlus, Search, UserPlus, Users } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { PageContainer } from '@/app/layout/PageContainer';
import { formatDate } from '@/core/utils/format';
import { Badge, StatusPill } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { buttonClasses } from '@/design-system/components/buttonStyles';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { EmptyState } from '@/design-system/components/EmptyState';
import { Input } from '@/design-system/components/Input';
import { PageHeader } from '@/design-system/components/PageHeader';
import { SegmentedControl } from '@/design-system/components/SegmentedControl';
import { Skeleton } from '@/design-system/components/Skeleton';
import { registerApi, registerKeys } from '../api/client';
import type { Crop } from '../api/types';
import { CROP_LABEL } from '../format';

/**
 * Dedicated page for finding an already-registered farmer by SAWIE ID, CNIC / ID number,
 * phone number, or name so an officer can quickly map a new field (or additional fields)
 * for any farmer they registered earlier.
 */
export default function AddFieldLookupPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [crop, setCrop] = useState<Crop | ''>('');
  const [onlyWithoutFields, setOnlyWithoutFields] = useState(false);

  const params = {
    q: q.trim() || undefined,
    crop: crop || undefined,
    page: 1,
    page_size: 100,
  };

  const farmersQuery = useQuery({
    queryKey: registerKeys.farmers(params),
    queryFn: ({ signal }) => registerApi.listFarmers(params, signal),
  });

  const allItems = farmersQuery.data?.items ?? [];
  const items = onlyWithoutFields ? allItems.filter((f) => !f.has_fields) : allItems;
  const unmappedCount = allItems.filter((f) => !f.has_fields).length;

  return (
    <PageContainer>
      <PageHeader
        title="Add Field to Farmer"
        subtitle="Enter a farmer's SAWIE ID, CNIC / ID number, phone number, or name to view their record and map new polygon fields."
        breadcrumb={[
          { label: 'Home', to: '/' },
          { label: 'Register Farmer', to: '/register' },
          { label: 'Add Field' },
        ]}
      />

      <Card padding="lg" className="mt-6">
        <SectionHeader
          title="Find registered farmer"
          description="Type SAWIE ID (e.g. 1001), CNIC (13 digits), phone number, or farmer name."
        />

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="min-w-[260px] flex-1">
            <Input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Enter SAWIE ID, CNIC / ID number, phone number, or farmer name..."
              leadingIcon={<Search />}
              aria-label="Search farmer by SAWIE ID, CNIC, phone, or name"
            />
          </div>

          <SegmentedControl
            aria-label="Crop filter"
            size="sm"
            value={crop || 'all'}
            onChange={(val) => setCrop(val === 'all' ? '' : (val as Crop))}
            options={[
              { value: 'all', label: 'All crops' },
              { value: 'cotton', label: 'Cotton' },
              { value: 'hemp', label: 'Hemp' },
            ]}
          />

          <Button
            type="button"
            variant={onlyWithoutFields ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setOnlyWithoutFields((v) => !v)}
          >
            Pending fields ({unmappedCount})
          </Button>
        </div>

        <div className="mt-6">
          {farmersQuery.isLoading ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : items.length === 0 ? (
            <EmptyState
              icon={<Users />}
              title={q.trim() ? 'No matching farmer found' : 'No farmers to show'}
              description={
                q.trim()
                  ? 'Check the SAWIE ID, CNIC, or phone number, or register this farmer first.'
                  : onlyWithoutFields
                    ? 'Every registered farmer already has at least one mapped field. Switch off "Pending fields" to add more fields to any farmer.'
                    : 'Register a farmer first, then come here any time to map their fields.'
              }
              action={
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {onlyWithoutFields && (
                    <Button variant="secondary" onClick={() => setOnlyWithoutFields(false)}>
                      Show all farmers
                    </Button>
                  )}
                  <Link to="/register/new" className={buttonClasses('primary', 'md')}>
                    <UserPlus className="h-4 w-4" aria-hidden />
                    <span>Register farmer</span>
                  </Link>
                </div>
              }
            />
          ) : (
            <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {items.map((farmer) => (
                <li
                  key={farmer.id}
                  className="flex flex-col justify-between gap-4 rounded-card border border-line bg-surface p-4 shadow-1 transition-colors hover:border-forest-500"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="mono-id rounded-sm bg-forest-50 px-2 py-0.5 text-sm font-semibold text-forest-800 border border-forest-100">
                          SAWIE #{farmer.sawie_id}
                        </span>
                        <Badge tone={farmer.crop === 'cotton' ? 'success' : 'accent'} size="sm">
                          {CROP_LABEL[farmer.crop]}
                        </Badge>
                        {farmer.has_fields ? (
                          <StatusPill tone="success">
                            {farmer.field_count} field{farmer.field_count === 1 ? '' : 's'} mapped
                          </StatusPill>
                        ) : (
                          <StatusPill tone="warning">No field yet</StatusPill>
                        )}
                      </div>
                      <h3 className="mt-2 truncate text-md font-semibold text-ink">
                        {farmer.name}
                      </h3>
                      <p className="text-sm text-muted">
                        {farmer.crop === 'cotton'
                          ? `S/O ${farmer.father_name ?? '-'}`
                          : (farmer.farm_name ?? '-')}
                        {' · '}
                        {farmer.location_summary}
                      </p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
                        <span>
                          ID / CNIC: <span className="mono-id text-ink">{farmer.id_number_masked}</span>
                        </span>
                        {farmer.phone_masked && (
                          <span>
                            Phone: <span className="mono-id text-ink">{farmer.phone_masked}</span>
                          </span>
                        )}
                        <span>Registered {formatDate(farmer.created_at)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line pt-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
                      onClick={() => navigate(`/register/farmers/${farmer.id}`)}
                    >
                      Profile
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      leftIcon={<MapPinPlus className="h-4 w-4" />}
                      onClick={() => navigate(`/register/farmers/${farmer.id}/fields/new`)}
                    >
                      {farmer.has_fields ? 'Add another field' : 'Add field'}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </PageContainer>
  );
}
