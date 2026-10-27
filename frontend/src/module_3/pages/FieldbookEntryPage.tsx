import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowRight, MapPinPlus, NotebookPen, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { PageContainer } from '@/app/layout/PageContainer';
import { toApiError } from '@/core/api/errors';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { cn } from '@/core/utils/cn';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  FormField,
  Input,
  NumberInput,
  PageHeader,
  SectionHeader,
  Skeleton,
  buttonClasses,
} from '@/design-system/components';
import { fieldbookApi, fieldbookKeys } from '../api/client';
import type { FarmerOption } from '../api/types';
import { FieldCards } from '../components/FieldCards';
import { OfficerSelect } from '../components/OfficerSelect';
import { SelectionDialog } from '../components/SelectionDialog';
import { bookPath } from '../lib/display';

const STATUS_BADGE: Record<string, { label: string; tone: 'neutral' | 'warning' | 'success' }> = {
  no_field: { label: 'No field mapped', tone: 'neutral' },
  not_started: { label: 'Not started', tone: 'neutral' },
  in_progress: { label: 'In progress', tone: 'warning' },
  submitted: { label: 'Submitted', tone: 'success' },
};

/**
 * Where an officer starts: choose officer, farmer, field and season, then open the
 * fieldbook. Now includes an inline interactive farmer & field picker on the page itself
 * in addition to the modal dialog so officers can search by SAWIE ID or name and open
 * any fieldbook directly.
 */
export default function FieldbookEntryPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const initialFarmerId = params.get('farmerId');
  const initialFieldId = params.get('fieldId');
  const me = useCurrentOfficer();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [officerId, setOfficerId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [season, setSeason] = useState<number>(new Date().getFullYear());
  const [selectedFarmer, setSelectedFarmer] = useState<FarmerOption | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(initialFieldId ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialFarmerId) setDialogOpen(true);
  }, [initialFarmerId]);

  const officers = useQuery({
    queryKey: fieldbookKeys.officers,
    queryFn: ({ signal }) => fieldbookApi.officers(signal),
  });

  useEffect(() => {
    if (officerId || !officers.data?.length) return;
    const self = officers.data.find((o) => o.id === me.data?.id);
    setOfficerId((self ?? officers.data[0])?.id ?? null);
  }, [officers.data, me.data, officerId]);

  const farmers = useQuery({
    queryKey: fieldbookKeys.farmers(officerId, search.trim(), season),
    queryFn: ({ signal }) =>
      fieldbookApi.farmers(officerId as string, search.trim() || undefined, season, signal),
    enabled: Boolean(officerId),
  });

  // Auto-select farmer when deep-linked or when only 1 farmer exists
  useEffect(() => {
    if (!farmers.data?.length) return;
    if (initialFarmerId && !selectedFarmer) {
      const match = farmers.data.find((f) => f.id === initialFarmerId);
      if (match) setSelectedFarmer(match);
    } else if (!selectedFarmer && farmers.data.length === 1) {
      setSelectedFarmer(farmers.data[0]!);
    }
  }, [farmers.data, initialFarmerId, selectedFarmer]);

  const activeFarmerId = selectedFarmer?.id ?? initialFarmerId ?? null;

  const fields = useQuery({
    queryKey: fieldbookKeys.fields(activeFarmerId, season),
    queryFn: ({ signal }) => fieldbookApi.fields(activeFarmerId as string, season, signal),
    enabled: Boolean(activeFarmerId),
  });

  useEffect(() => {
    const items = fields.data?.items ?? [];
    if (items.length === 1 && !selectedFieldId) {
      setSelectedFieldId(items[0]!.id);
    } else if (selectedFieldId && items.length && !items.some((f) => f.id === selectedFieldId)) {
      setSelectedFieldId(items[0]?.id ?? null);
    }
  }, [fields.data, selectedFieldId]);

  const openBook = useMutation({
    mutationFn: () => fieldbookApi.open(selectedFieldId as string, season),
    onSuccess: (book) => {
      navigate(bookPath(book.id, book.locked));
    },
    onError: (e) => setError(toApiError(e).message),
  });

  return (
    <PageContainer>
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Fieldbook"
          subtitle="A season diary for each field, filled in step by step and locked on submit."
        />

        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          {/* Left column: Pick Officer, Season & Farmer */}
          <Card padding="lg" className="flex flex-col gap-4">
            <SectionHeader
              title="1. Select Farmer"
              description="Search by SAWIE ID or farmer name to view their mapped fields."
            />

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_112px]">
              {me.data?.role !== 'officer' && (
                <FormField label="Field officer">
                  <OfficerSelect
                    officers={officers.data ?? []}
                    value={officerId}
                    loading={officers.isLoading}
                    onChange={(id) => {
                      setOfficerId(id);
                      setSelectedFarmer(null);
                      setSelectedFieldId(null);
                    }}
                  />
                </FormField>
              )}

              <div className="w-28 max-w-full">
              <FormField label="Season year">
                <NumberInput
                  value={season}
                  onValueChange={(v) => setSeason(v ?? new Date().getFullYear())}
                  decimals={0}
                  min={2000}
                  max={2100}
                  className="!text-left"
                />
              </FormField>
              </div>
            </div>

            <FormField label="Search farmer" required>
              <Input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Type SAWIE ID or farmer name..."
                leadingIcon={<Search />}
              />
            </FormField>

            <div className="max-h-[380px] overflow-y-auto rounded-card border border-line bg-canvas/50 p-2">
              {farmers.isLoading ? (
                <div className="flex flex-col gap-2 p-2">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                </div>
              ) : !farmers.data || farmers.data.length === 0 ? (
                <EmptyState
                  compact
                  title="No farmers found"
                  description="Register a farmer and map their field first."
                  action={
                    <Link to="/register/new" className={buttonClasses('primary', 'sm')}>
                      Register farmer
                    </Link>
                  }
                />
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {farmers.data.map((farmer) => {
                    const active = selectedFarmer?.id === farmer.id;
                    const badge = STATUS_BADGE[farmer.fieldbook_status] ?? STATUS_BADGE.not_started!;
                    return (
                      <li key={farmer.id}>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedFarmer(farmer);
                            setSelectedFieldId(null);
                            setError(null);
                          }}
                          className={cn(
                            'flex w-full items-center justify-between gap-3 rounded-control border px-3.5 py-2.5 text-left transition-colors',
                            active
                              ? 'border-forest-600 bg-forest-50 text-ink ring-1 ring-forest-500/30'
                              : 'border-line bg-surface text-ink hover:bg-canvas',
                          )}
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="mono-id text-xs font-semibold text-forest-800">
                                SAWIE #{farmer.sawie_id}
                              </span>
                              <span className="truncate font-semibold text-ink">{farmer.name}</span>
                            </div>
                            <span className="mt-0.5 block text-xs text-muted">
                              {farmer.field_count} field{farmer.field_count === 1 ? '' : 's'} mapped
                              {farmer.drafts > 0 ? ` · ${farmer.drafts} draft` : ''}
                              {farmer.submitted > 0 ? ` · ${farmer.submitted} submitted` : ''}
                            </span>
                          </div>
                          <Badge size="sm" tone={badge.tone}>
                            {badge.label}
                          </Badge>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </Card>

          {/* Right column: Pick Field & Open Fieldbook */}
          <Card padding="lg" className="flex flex-col gap-4">
            <SectionHeader
              title="2. Choose Field & Open Fieldbook"
              description={
                selectedFarmer
                  ? `Fields mapped for ${selectedFarmer.name} (SAWIE #${selectedFarmer.sawie_id})`
                  : 'Select a farmer on the left to see their mapped fields.'
              }
              actions={
                activeFarmerId ? (
                  <Link
                    to={`/register/farmers/${activeFarmerId}/fields/new`}
                    className={buttonClasses('secondary', 'sm')}
                  >
                    <MapPinPlus className="h-3.5 w-3.5" aria-hidden />
                    <span>Add field</span>
                  </Link>
                ) : undefined
              }
            />

            {!activeFarmerId ? (
              <EmptyState
                compact
                icon={<NotebookPen className="h-5 w-5" />}
                title="Select a farmer first"
                description="Click any farmer in the list on the left to view their mapped fields and open their fieldbook."
              />
            ) : fields.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : fields.data ? (
              <>
                <FieldCards
                  farmerId={activeFarmerId}
                  crop={fields.data.farmer.crop}
                  fields={fields.data.items}
                  value={selectedFieldId}
                  onChange={(id) => {
                    setSelectedFieldId(id);
                    setError(null);
                  }}
                />

                {error && (
                  <p role="alert" className="rounded-control bg-danger-tint px-3 py-2 text-sm text-danger">
                    {error}
                  </p>
                )}

                {fields.data.items.length > 0 && (
                  <div className="mt-2 flex items-center justify-end border-t border-line pt-4">
                    <Button
                      rightIcon={<ArrowRight className="h-4 w-4" />}
                      disabled={!selectedFieldId || !season}
                      loading={openBook.isPending}
                      onClick={() => {
                        setError(null);
                        openBook.mutate();
                      }}
                    >
                      Open fieldbook
                    </Button>
                  </div>
                )}
              </>
            ) : null}
          </Card>
        </div>

        <SelectionDialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          initialFarmerId={initialFarmerId}
          initialFieldId={initialFieldId}
        />
      </div>
    </PageContainer>
  );
}
