import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  Info,
  Layers,
  MapPinPlus,
  NotebookPen,
  Save,
} from 'lucide-react';
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { PageContainer } from '@/app/layout/PageContainer';
import { ApiError } from '@/core/api/errors';
import { formatDecimal, formatNumber } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Card } from '@/design-system/components/Card';
import { PageHeader } from '@/design-system/components/PageHeader';
import { Skeleton } from '@/design-system/components/Skeleton';
import { toast } from '@/design-system/components/toastStore';
import { registerApi, registerKeys } from '../api/client';
import type { Field } from '../api/types';
import { FarmerSummaryCard } from '../components/FarmerSummaryCard';
import type { DraftState, FieldMapHandle } from '../components/FieldMap';

const FieldMap = lazy(() => import('../components/FieldMap').then((m) => ({ default: m.FieldMap })));
import { FieldRail } from '../components/FieldRail';
import { FieldTable } from '../components/FieldTable';
import { MapToolbar } from '../components/MapToolbar';
import { OverlapAlert } from '../components/OverlapAlert';
import { SawieIdChip } from '../components/SawieIdChip';
import { VertexDrawer } from '../components/VertexDrawer';
import { useFieldValidation } from '../hooks/useFieldValidation';
import { useGeolocation } from '../hooks/useGeolocation';
import { useMapStore } from '../store/mapStore';

const EMPTY_DRAFT: DraftState = { geometry: null, pin: null };

export default function FieldMapPage() {
  const { farmerId = '', fieldId } = useParams<{ farmerId: string; fieldId?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const editing = Boolean(fieldId);

  const mapHandle = useRef<FieldMapHandle | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState<DraftState>(EMPTY_DRAFT);
  const [tools, setTools] = useState({ drawing: false, editing: false });
  const [fullscreen, setFullscreen] = useState(false);
  const [vertexField, setVertexField] = useState<Field | null>(null);
  const [savedField, setSavedField] = useState<Field | null>(null);

  /* A saved field belongs to one farmer: opening another farmer must not keep its
     measurements or the "saved" card on screen. */
  useEffect(() => {
    setSavedField(null);
  }, [farmerId]);

  const selectedFieldId = useMapStore((s) => s.selectedFieldId);
  const selectField = useMapStore((s) => s.selectField);
  const resetMapUi = useMapStore((s) => s.reset);

  const geo = useGeolocation();
  const validation = useFieldValidation(farmerId, fieldId ?? null);

  const profile = useQuery({
    queryKey: registerKeys.profile(farmerId),
    queryFn: ({ signal }) => registerApi.getFarmerProfile(farmerId, signal),
    enabled: Boolean(farmerId),
  });

  const fields = useQuery({
    queryKey: registerKeys.fields(farmerId),
    queryFn: ({ signal }) => registerApi.listFarmerFields(farmerId, signal),
    enabled: Boolean(farmerId),
  });

  /* Ask for the officer's position once, when the page opens. */
  useEffect(() => {
    geo.locate();
    return () => resetMapUi();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Load the field being reshaped into the draft, so the map opens on its boundary. */
  const loadedField = useRef<string | null>(null);
  useEffect(() => {
    if (!fieldId || !fields.data || loadedField.current === fieldId) return;
    const existing = fields.data.items.find((item) => item.id === fieldId);
    if (!existing) return;
    loadedField.current = fieldId;
    setDraft({ geometry: existing.geometry, pin: { lat: existing.pin_lat, lng: existing.pin_lng } });
    selectField(existing.id);
    window.setTimeout(() => mapHandle.current?.fitField(existing), 150);
  }, [fieldId, fields.data, selectField]);

  /* Auto-fit all saved fields of this farmer when opening the Add Field screen. */
  const autoFittedFarmer = useRef<string | null>(null);
  useEffect(() => {
    if (fieldId || !fields.data || autoFittedFarmer.current === farmerId) return;
    if (fields.data.items.length > 0) {
      autoFittedFarmer.current = farmerId;
      window.setTimeout(() => mapHandle.current?.fitAllFields(), 200);
    }
  }, [fieldId, farmerId, fields.data]);

  /* Every change to the boundary is re-checked by the server, which is what the Save
     button follows. Nothing is trusted from the client's own geometry. */
  useEffect(() => {
    validation.check(draft.geometry, draft.pin);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.geometry, draft.pin]);

  const save = useMutation({
    mutationFn: async () => {
      if (!draft.geometry) throw new Error('Draw a boundary first.');
      const body = {
        geometry: draft.geometry,
        pin_lat: draft.pin?.lat ?? null,
        pin_lng: draft.pin?.lng ?? null,
      };
      return fieldId
        ? registerApi.updateField(fieldId, body)
        : registerApi.createField(farmerId, body);
    },
    onSuccess: (field) => {
      void queryClient.invalidateQueries({ queryKey: registerKeys.all });
      setSavedField(field);
      setDraft(EMPTY_DRAFT);
      validation.reset();
      selectField(field.id);
      toast.success(
        fieldId ? 'Field updated' : 'Field saved',
        `${field.field_id}, ${formatDecimal(field.area_acre, 2)} acres.`,
      );
      if (fieldId) navigate(`/register/farmers/${farmerId}/fields/new`, { replace: true });
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'The field could not be saved.';
      toast.error(fieldId ? 'Could not update the field' : 'Could not save the field', message);
    },
  });

  const remove = useMutation({
    mutationFn: (field: Field) => registerApi.deleteField(field.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: registerKeys.all });
      toast.success('Field removed', 'Its field ID will not be reused.');
    },
    onError: (error) => {
      // A guard denial arrives as a 409 naming every reason a later module gave.
      const message =
        error instanceof ApiError ? error.message : 'The field could not be removed.';
      toast.error('Could not remove the field', message);
    },
  });

  const onFullscreen = useCallback(() => {
    const element = containerRef.current;
    if (!element) return;
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void element.requestFullscreen?.().catch(() => undefined);
    }
  }, []);

  useEffect(() => {
    const onChange = () => {
      setFullscreen(Boolean(document.fullscreenElement));
      mapHandle.current?.invalidate();
    };
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const farmer = profile.data?.farmer;
  const items = fields.data?.items ?? [];
  const nextFieldId = fields.data?.next_field_id_preview ?? '';
  const result = validation.result;

  /* After a save the draft is empty, so the measurements come from the saved field
     instead of resetting to dashes. */
  const savedStats =
    !draft.geometry && savedField
      ? { area: savedField.area_acre, corners: savedField.vertex_count, saved: true as const }
      : null;

  const startNew = () => {
    setSavedField(null);
    setDraft(EMPTY_DRAFT);
    validation.reset();
    loadedField.current = null;
    if (fieldId) navigate(`/register/farmers/${farmerId}/fields/new`);
    mapHandle.current?.startDraw();
  };

  if (profile.isLoading || !farmer) {
    return (
      <PageContainer wide>
        <Skeleton className="h-8 w-72" shape="block" />
        <Skeleton className="mt-6 h-[560px]" shape="block" />
      </PageContainer>
    );
  }

  return (
    <PageContainer wide>
      <PageHeader
        title={farmer.name}
        subtitle={editing ? 'Reshape a mapped field.' : "Map this farmer's fields (draw one or multiple polygons)."}
        breadcrumb={[
          { label: 'Register Farmer', to: '/register' },
          { label: farmer.name, to: `/register/farmers/${farmer.id}` },
          { label: editing ? 'Edit field' : 'Add field' },
        ]}
        actions={
          <span className="flex flex-wrap items-center gap-2">
            <SawieIdChip sawieId={farmer.sawie_id} />
            <span className="inline-flex items-baseline gap-2 rounded-pill border border-line bg-canvas px-3 py-1">
              <span className="text-xs font-medium text-muted">Field ID</span>
              <span className="mono-id text-md font-semibold text-ink">
                {editing
                  ? (items.find((item) => item.id === fieldId)?.field_id ?? '')
                  : nextFieldId}
              </span>
              {!editing && <span className="text-xs text-muted">Assigned on save</span>}
            </span>
          </span>
        }
      />

      {geo.message && (
        <p className="mt-4 flex items-center gap-2 text-sm text-muted">
          <Info className="h-4 w-4 shrink-0 text-wheat-600" aria-hidden />
          {geo.message}
        </p>
      )}

      <div className="mt-6 flex flex-col gap-5">
        <aside className="flex flex-col gap-3">
          <FieldRail
            fields={items}
            selectedFieldId={selectedFieldId}
            nextFieldId={nextFieldId}
            drafting={Boolean(draft.geometry) || tools.drawing}
            editingFieldId={fieldId ?? null}
            onStartNew={startNew}
            onSelect={(id) => {
              selectField(id);
              const field = items.find((item) => item.id === id);
              if (field) mapHandle.current?.fitField(field);
            }}
          />
          {items.length > 0 && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              leftIcon={<Layers className="h-4 w-4" />}
              onClick={() => mapHandle.current?.fitAllFields()}
            >
              Show all {items.length} mapped field{items.length === 1 ? '' : 's'}
            </Button>
          )}
        </aside>

        <div className="flex min-w-0 flex-col gap-4">
          <MapToolbar
            hasDraft={Boolean(draft.geometry)}
            drawing={tools.drawing}
            editing={tools.editing}
            fullscreen={fullscreen}
            locating={geo.status === 'locating'}
            onDraw={() => mapHandle.current?.startDraw()}
            onCancelDraw={() => mapHandle.current?.cancelDraw()}
            onEdit={() => mapHandle.current?.toggleEdit()}
            onPin={() => mapHandle.current?.startPin()}
            onDelete={() => mapHandle.current?.deleteDraft()}
            onUndo={() => mapHandle.current?.undoVertex()}
            onLocate={() => {
              geo.locate();
              if (geo.position) mapHandle.current?.flyTo(geo.position.lat, geo.position.lng, 18);
            }}
            onFullscreen={onFullscreen}
          />

          <div
            ref={containerRef}
            className="relative h-[60vh] min-h-[400px] w-full overflow-hidden rounded-card border border-line bg-canvas shadow-1 sm:h-[70vh] lg:h-[75vh]"
          >
            <Suspense fallback={<Skeleton className="h-full w-full" shape="block" />}>
              <FieldMap
                key={farmerId}
                farmerId={farmerId}
                farmerName={farmer.name}
                farmerSawieId={farmer.sawie_id}
                country={farmer.country}
                farmerFields={items}
                editingFieldId={fieldId ?? null}
                draft={draft}
                onDraftChange={setDraft}
                conflicts={result?.conflicts ?? []}
                position={geo.position}
                selectedFieldId={selectedFieldId}
                onSelectField={selectField}
                handleRef={mapHandle}
                onToolChange={setTools}
              />
            </Suspense>
          </div>

          {/* Live measurements while drawing. */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-card border border-line bg-surface px-4 py-3">
            <Measure
              label="Area"
              value={
                result?.area_acre != null
                  ? `${formatDecimal(result.area_acre, 2)} acres`
                  : savedStats
                    ? `${formatDecimal(savedStats.area, 2)} acres`
                    : draft.geometry
                      ? 'Measuring'
                      : '-'
              }
            />
            <Measure
              label="Corners"
              value={
                result?.vertex_count != null
                  ? formatNumber(result.vertex_count)
                  : savedStats
                    ? formatNumber(savedStats.corners)
                    : '-'
              }
            />
            <Measure
              label="Pin"
              value={draft.pin || savedStats ? 'Placed' : 'Centre of the field'}
            />
            <span className="ml-auto">
              {validation.checking ? (
                <Badge tone="neutral">Checking</Badge>
              ) : savedStats ? (
                <Badge tone="success">Saved</Badge>
              ) : validation.canSave ? (
                <Badge tone="success">No overlap</Badge>
              ) : draft.geometry ? (
                <Badge tone="danger">Cannot save</Badge>
              ) : (
                <Badge tone="neutral">Nothing drawn</Badge>
              )}
            </span>
          </div>

          <OverlapAlert validation={result} checking={validation.checking} />

          {savedField ? (
            <Card padding="md" className="border-forest-100 bg-forest-50">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-base text-ink">
                  Field <span className="mono-id font-medium">{savedField.field_id}</span> saved,{' '}
                  {formatDecimal(savedField.area_acre, 2)} acres. Add another field for this
                  farmer, switch to another farmer, or open the fieldbook.
                </p>
                <span className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="primary"
                    leftIcon={<MapPinPlus className="h-4 w-4" />}
                    onClick={startNew}
                  >
                    Add another field
                  </Button>
                  <Button
                    variant="secondary"
                    rightIcon={<ArrowRight className="h-4 w-4" />}
                    onClick={() => navigate(`/fieldbook?farmerId=${farmerId}&fieldId=${savedField.id}`)}
                  >
                    Open fieldbook
                  </Button>
                </span>
              </div>
            </Card>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
              {items.length > 0 && (
                <Button
                  variant="secondary"
                  leftIcon={<NotebookPen className="h-4 w-4" />}
                  onClick={() => navigate(`/fieldbook?farmerId=${farmerId}`)}
                >
                  Open fieldbook
                </Button>
              )}
            </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="secondary" onClick={() => navigate(`/register/farmers/${farmerId}`)}>
                  View farmer profile
                </Button>
                <Button
                  leftIcon={<Save className="h-4 w-4" />}
                  loading={save.isPending}
                  disabled={!validation.canSave}
                  onClick={() => save.mutate()}
                >
                  {editing ? 'Save boundary' : 'Save field'}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-8 flex flex-col gap-5">
        <FarmerSummaryCard
          farmer={farmer}
          season={profile.data?.season_profiles[0] ?? null}
          readOnlyNotice
        />
        <FieldTable
          fields={items}
          loading={fields.isLoading}
          selectedFieldId={selectedFieldId}
          deleting={remove.isPending}
          onSelect={selectField}
          onLocate={(field) => {
            selectField(field.id);
            mapHandle.current?.fitField(field);
          }}
          onEdit={(field) => navigate(`/register/farmers/${farmerId}/fields/${field.id}/edit`)}
          onDelete={(field) => remove.mutate(field)}
          onShowVertices={setVertexField}
        />
      </div>

      <VertexDrawer
        field={vertexField}
        open={vertexField !== null}
        onClose={() => setVertexField(null)}
      />
    </PageContainer>
  );
}

function Measure({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex flex-col">
      <span className="text-xs font-medium text-muted">{label}</span>
      <span className="tabular text-base font-medium text-ink">{value}</span>
    </span>
  );
}
