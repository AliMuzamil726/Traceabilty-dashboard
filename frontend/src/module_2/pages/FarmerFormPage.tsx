import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { MapPinPlus, UserPlus } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate, useParams } from 'react-router-dom';
import { PageContainer } from '@/app/layout/PageContainer';
import { ApiError } from '@/core/api/errors';
import { useCurrentOfficer, useMasterList } from '@/core/hooks/useSharedData';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { ChoiceCards } from '@/design-system/components/ChoiceCards';
import { ConfirmDialog } from '@/design-system/components/ConfirmDialog';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { PageHeader } from '@/design-system/components/PageHeader';
import { Select } from '@/design-system/components/Select';
import { toast } from '@/design-system/components/toastStore';
import { registerApi, registerKeys } from '../api/client';
import {
  CROP_SPECIFIC_FIELDS,
  TEHSIL_OTHER,
  defaultsForCrop,
  farmerFormSchema,
  type FarmerFormValues,
} from '../api/schemas';
import type { Crop, FarmerInput } from '../api/types';
import { CropSwitch } from '../components/CropSwitch';
import { ExistingFarmerBanner } from '../components/ExistingFarmerBanner';
import { IdNumberInput } from '../components/IdNumberInput';
import { LocationCascade } from '../components/LocationCascade';
import { PhoneInput } from '../components/PhoneInput';
import { PostcodeLookup } from '../components/PostcodeLookup';
import { SawieIdChip } from '../components/SawieIdChip';
import { CROP_COUNTRY } from '../format';
import { useFarmerLookup, isLookupReady } from '../hooks/useFarmerLookup';
import { useFieldOffices } from '../hooks/useFieldOffices';

/** Turn the flat form values into the request body for the crop that was chosen. */
function toPayload(values: FarmerFormValues): FarmerInput {
  const shared = {
    crop: values.crop,
    id_number: values.id_number,
    name: values.name,
    field_office_id: values.field_office_id,
    phone: values.phone || null,
    variety: values.variety,
    tenure: values.tenure,
    previous_crop: values.previous_crop || null,
  };
  if (values.crop === 'cotton') {
    const chosen = values.tehsil_code.trim();
    return {
      ...shared,
      father_name: values.father_name,
      province_code: values.province_code,
      district_code: values.district_code,
      // "Other" is a UI choice, not a location: send the typed name instead.
      tehsil_code: chosen && chosen !== TEHSIL_OTHER ? chosen : null,
      tehsil_name: chosen && chosen !== TEHSIL_OTHER ? null : values.tehsil_name,
      village: values.village,
    };
  }
  return {
    ...shared,
    farm_name: values.farm_name,
    home_office_licence_no: values.home_office_licence_no,
    postcode: values.postcode,
    county: values.postcode_manual ? values.county : null,
    region: values.postcode_manual ? values.region : null,
  };
}

export default function FarmerFormPage() {
  const { farmerId } = useParams<{ farmerId?: string }>();
  const editing = Boolean(farmerId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const officer = useCurrentOfficer();
  const isFieldOfficer = officer.data?.role === 'officer';
  const [leaving, setLeaving] = useState<string | null>(null);
  const [savedRedirecting, setSavedRedirecting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const form = useForm<FarmerFormValues>({
    resolver: zodResolver(farmerFormSchema),
    defaultValues: defaultsForCrop('cotton'),
    mode: 'onBlur',
  });
  const { register, handleSubmit, watch, setValue, formState, reset, setError } = form;
  const values = watch();
  const crop = values.crop;
  const country = CROP_COUNTRY[crop];

  const offices = useFieldOffices(country);
  const varieties = useMasterList('variety', { country, crop });
  const tenures = useMasterList('tenure', { country, crop });
  const previousCrops = useMasterList('previous_crop', { country });

  const lookup = useFarmerLookup(values.id_number, crop);
  const existing = lookup.data?.exists ? lookup.data : null;
  const blocked = Boolean(lookup.data?.crop_mismatch);

  /* Default the field office to the officer's own, once, and only while it is unset. */
  useEffect(() => {
    const own = officer.data?.field_office_id;
    if (!own || values.field_office_id) return;
    if (offices.data?.some((o) => o.id === own)) setValue('field_office_id', own);
  }, [officer.data, offices.data, values.field_office_id, setValue]);

  /* Pre-fill the personal half from an existing farmer. Crop data is never filled in:
     the officer enters this season's variety, tenure and previous crop. */
  const filledFor = useRef<string | null>(null);
  useEffect(() => {
    const personal = lookup.data?.personal;
    const key = lookup.data?.farmer_id ?? null;
    if (!personal || !key || filledFor.current === key) return;
    filledFor.current = key;
    setValue('name', personal.name, { shouldDirty: false });
    setValue('phone', personal.phone ?? '', { shouldDirty: false });
    if (crop === 'cotton') {
      setValue('father_name', personal.father_name ?? '', { shouldDirty: false });
      setValue('province_code', personal.province_code ?? '', { shouldDirty: false });
      setValue('district_code', personal.district_code ?? '', { shouldDirty: false });
      setValue('tehsil_code', personal.tehsil_code ?? TEHSIL_OTHER, { shouldDirty: false });
      setValue('tehsil_name', personal.tehsil_code ? '' : (personal.tehsil ?? ''), {
        shouldDirty: false,
      });
      setValue('village', personal.village ?? '', { shouldDirty: false });
    } else {
      setValue('farm_name', personal.farm_name ?? '', { shouldDirty: false });
      setValue('home_office_licence_no', personal.home_office_licence_no ?? '', {
        shouldDirty: false,
      });
      setValue('postcode', personal.postcode ?? '', { shouldDirty: false });
      setValue('county', personal.county ?? '', { shouldDirty: false });
      setValue('region', personal.region ?? '', { shouldDirty: false });
    }
    if (personal.field_office_id) {
      setValue('field_office_id', personal.field_office_id, { shouldDirty: false });
    }
  }, [lookup.data, crop, setValue]);

  /* Load the farmer being edited. */
  useEffect(() => {
    if (!farmerId) return;
    let cancelled = false;
    void registerApi.getFarmerProfile(farmerId).then((profile) => {
      if (cancelled) return;
      const farmer = profile.farmer;
      const season = profile.season_profiles[0];
      reset({
        ...defaultsForCrop(farmer.crop),
        name: farmer.name,
        id_number: farmer.sensitive_visible ? farmer.id_number : '',
        phone: farmer.sensitive_visible ? (farmer.phone ?? '') : '',
        father_name: farmer.father_name ?? '',
        farm_name: farmer.farm_name ?? '',
        home_office_licence_no: farmer.home_office_licence_no ?? '',
        postcode: farmer.postcode ?? '',
        county: farmer.county ?? '',
        region: farmer.region ?? '',
        village: farmer.village ?? '',
        field_office_id: farmer.field_office?.id ?? '',
        variety: season?.variety ?? '',
        tenure: season?.tenure ?? '',
        previous_crop: season?.previous_crop ?? '',
      });
    });
    return () => {
      cancelled = true;
    };
  }, [farmerId, reset]);

  const save = useMutation({
    mutationFn: (payload: FarmerInput) =>
      farmerId ? registerApi.updateFarmer(farmerId, payload) : registerApi.createFarmer(payload),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: registerKeys.all });
      setSavedRedirecting(true);
      toast.success(
        result.created ? 'Farmer registered' : 'Farmer updated',
        `SAWIE ID ${result.farmer.sawie_id} — opening field map.`,
      );
      // Immediately move to the field mapping page so the officer can draw polygons right away
      // or click "Register another farmer" from the banner on the field page.
      navigate(
        `/register/farmers/${result.farmer.id}/fields/new?justRegistered=${result.created ? '1' : '0'}`,
        { replace: true },
      );
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        // 422 bodies carry per-field messages; put each one on its own field.
        const fieldErrors = error.fieldErrors;
        const keys = Object.keys(fieldErrors);
        if (keys.length > 0) {
          for (const key of keys) {
            setError(key as keyof FarmerFormValues, {
              type: 'server',
              message: fieldErrors[key],
            });
          }
          toast.error('Check the highlighted fields', error.message);
          return;
        }
      }
      toast.error('Could not save the farmer', error instanceof Error ? error.message : undefined);
    },
  });

  const onCropChange = useCallback(
    (next: Crop) => {
      for (const key of CROP_SPECIFIC_FIELDS) {
        setValue(key, '' as never, { shouldDirty: false });
      }
      setValue('postcode_manual', false);
      setValue('crop', next, { shouldDirty: false });
      filledFor.current = null;
    },
    [setValue],
  );

  const dirty = formState.isDirty || Boolean(values.id_number) || Boolean(values.name);
  const unsavedChanges = dirty && !savedRedirecting;

  /* Warn before leaving with unsaved work (the browser-level guard; in-app links go
     through the Cancel button, which asks the same question). */
  useEffect(() => {
    if (!unsavedChanges) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [unsavedChanges]);

  const leave = (to: string) => {
    if (unsavedChanges) setLeaving(to);
    else navigate(to);
  };

  const officeOptions = useMemo(
    () => (offices.data ?? []).map((office) => ({ value: office.id, label: office.name })),
    [offices.data],
  );

  const errors = formState.errors;
  const isCotton = crop === 'cotton';

  return (
    <PageContainer>
      <PageHeader
        title={editing ? 'Edit farmer' : 'Register farmer'}
        subtitle={
          editing
            ? "Correct this farmer's details and record this season."
            : 'Choose the crop programme, enter the farmer, then map their fields.'
        }
        breadcrumb={[
          { label: 'Home', to: '/' },
          { label: 'Register Farmer', to: '/register' },
          { label: editing ? 'Edit' : 'New' },
        ]}
        actions={
          isFieldOfficer && officer.data ? (
            <span className="inline-flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-1.5 text-sm text-ink">
              <span className="text-muted">Field officer</span>
              <span className="font-medium">{officer.data.full_name}</span>
            </span>
          ) : undefined
        }
      />

      <form
        ref={formRef}
        noValidate
        onSubmit={handleSubmit((submitted) => save.mutate(toPayload(submitted)))}
        className="mt-6 flex flex-col gap-6 pb-10"
      >
        <Card padding="lg">
          <SectionHeader
            title="Crop programme"
            description="The crop decides the country, the details asked for and the lists offered."
          />
          <div className="mt-4">
            <CropSwitch
              value={crop}
              onChange={onCropChange}
              dirty={dirty}
              disabled={editing || save.isPending}
            />
          </div>
        </Card>

        <Card padding="lg">
          <SectionHeader title="Identity" />
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <FormField
                label={isCotton ? 'CNIC' : 'ID number'}
                required
                error={errors.id_number?.message}
                hint={
                  isCotton
                    ? '13 digits, formatted as you type'
                    : '9 to 13 digits, grouped as you type'
                }
              >
                <IdNumberInput
                  crop={crop}
                  value={values.id_number}
                  invalid={Boolean(errors.id_number)}
                  disabled={save.isPending}
                  onChange={(next) => setValue('id_number', next, { shouldDirty: true })}
                />
              </FormField>
              <div aria-live="polite" className="min-h-[28px]">
                <SawieIdChip
                  loading={lookup.isFetching && isLookupReady(values.id_number, crop)}
                  sawieId={lookup.data?.sawie_id ?? lookup.data?.next_sawie_id_preview ?? null}
                  preview={!existing}
                />
              </div>
            </div>

            <FormField
              label={isCotton ? 'Name' : 'Farmer name'}
              required
              error={errors.name?.message}
            >
              <Input
                autoComplete="off"
                disabled={save.isPending}
                invalid={Boolean(errors.name)}
                {...register('name', {
                  onBlur: (event) => {
                    // Title case on blur, so typing is never fought with.
                    const titled = titleCase(event.target.value);
                    if (titled !== event.target.value) setValue('name', titled);
                  },
                })}
              />
            </FormField>

            {isCotton ? (
              <FormField label="Father name" required error={errors.father_name?.message}>
                <Input
                  autoComplete="off"
                  disabled={save.isPending}
                  invalid={Boolean(errors.father_name)}
                  {...register('father_name', {
                    onBlur: (event) => {
                      const titled = titleCase(event.target.value);
                      if (titled !== event.target.value) setValue('father_name', titled);
                    },
                  })}
                />
              </FormField>
            ) : (
              <FormField label="Farm name" required error={errors.farm_name?.message}>
                <Input
                  autoComplete="off"
                  disabled={save.isPending}
                  invalid={Boolean(errors.farm_name)}
                  {...register('farm_name')}
                />
              </FormField>
            )}

            {!isCotton && (
              <FormField
                label="Home Office hemp licence number"
                required
                error={errors.home_office_licence_no?.message}
                hint="Letters, digits and dashes"
              >
                <Input
                  mono
                  autoComplete="off"
                  disabled={save.isPending}
                  invalid={Boolean(errors.home_office_licence_no)}
                  {...register('home_office_licence_no', {
                    onChange: (event) =>
                      setValue('home_office_licence_no', event.target.value.toUpperCase()),
                  })}
                />
              </FormField>
            )}
          </div>

          {lookup.data && <div className="mt-5">{<ExistingFarmerBanner lookup={lookup.data} />}</div>}
        </Card>

        <Card padding="lg">
          <SectionHeader title="Contact" />
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            <FormField label="Phone" required={isCotton} error={errors.phone?.message} hint={isCotton ? '11-digit Pakistani mobile, e.g. 0300-1234567' : 'Optional — UK mobile'}>
              <PhoneInput
                crop={crop}
                value={values.phone}
                invalid={Boolean(errors.phone)}
                disabled={save.isPending}
                onChange={(next) => setValue('phone', next, { shouldDirty: true })}
              />
            </FormField>
          </div>
        </Card>

        <Card padding="lg">
          <SectionHeader title={isCotton ? 'Location' : 'Farm and location'} />
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            {isCotton ? (
              <LocationCascade
                country={country}
                disabled={save.isPending}
                value={{
                  province_code: values.province_code,
                  district_code: values.district_code,
                  tehsil_code: values.tehsil_code,
                  tehsil_name: values.tehsil_name,
                  village: values.village,
                }}
                onChange={(next) => {
                  setValue('province_code', next.province_code, { shouldDirty: true });
                  setValue('district_code', next.district_code, { shouldDirty: true });
                  setValue('tehsil_code', next.tehsil_code, { shouldDirty: true });
                  setValue('tehsil_name', next.tehsil_name, { shouldDirty: true });
                  setValue('village', next.village, { shouldDirty: true });
                }}
                errors={{
                  province_code: errors.province_code?.message,
                  district_code: errors.district_code?.message,
                  tehsil_code: errors.tehsil_code?.message,
                  tehsil_name: errors.tehsil_name?.message,
                  village: errors.village?.message,
                }}
              />
            ) : (
              <PostcodeLookup
                disabled={save.isPending}
                onManualChange={(manual) => setValue('postcode_manual', manual)}
                value={{
                  postcode: values.postcode,
                  county: values.county,
                  region: values.region,
                }}
                onChange={(next) => {
                  setValue('postcode', next.postcode, { shouldDirty: true });
                  setValue('county', next.county, { shouldDirty: true });
                  setValue('region', next.region, { shouldDirty: true });
                }}
                errors={{
                  postcode: errors.postcode?.message,
                  county: errors.county?.message,
                  region: errors.region?.message,
                }}
              />
            )}

            <FormField label="Field office" required error={errors.field_office_id?.message}>
              <Select
                placeholder="Choose a field office"
                disabled={save.isPending || offices.isLoading}
                options={officeOptions}
                {...register('field_office_id')}
              />
            </FormField>
          </div>
        </Card>

        <Card padding="lg">
          <SectionHeader
            title="Crop details"
            description="These belong to this season and are not carried over from last time."
          />
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            <FormField label="Variety" required error={errors.variety?.message}>
              <Select
                placeholder={varieties.isLoading ? 'Loading varieties' : 'Choose a variety'}
                disabled={save.isPending || varieties.isLoading}
                options={(varieties.data?.items ?? []).map((item) => ({
                  value: item.value,
                  label: item.label,
                }))}
                {...register('variety')}
              />
            </FormField>

            <FormField label="Previous crop" error={errors.previous_crop?.message}>
              <Select
                placeholder={previousCrops.isLoading ? 'Loading crops' : 'Choose the previous crop'}
                disabled={save.isPending || previousCrops.isLoading}
                options={(previousCrops.data?.items ?? []).map((item) => ({
                  value: item.value,
                  label: item.label,
                }))}
                {...register('previous_crop')}
              />
            </FormField>

            <div className="md:col-span-2">
              <FormField label="Land tenure" required error={errors.tenure?.message}>
                <ChoiceCards
                  aria-label="Land tenure"
                  columns={3}
                  invalid={Boolean(errors.tenure)}
                  value={values.tenure || null}
                  onChange={(next) => setValue('tenure', next, { shouldDirty: true })}
                  options={(tenures.data?.items ?? []).map((item) => ({
                    value: item.value,
                    title: item.label,
                  }))}
                />
              </FormField>
            </div>
          </div>

          {/* Inline submit actions directly inside the Crop Details card so they are always visible */}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
            <div className="flex items-center gap-2 text-sm text-muted">
              {blocked ? (
                <Badge tone="danger">Blocked: farmer is in the other programme</Badge>
              ) : existing ? (
                <Badge tone="info">Updating SAWIE ID {existing.sawie_id}</Badge>
              ) : (
                <span>The SAWIE ID is assigned when you save, then the field map opens.</span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {existing?.farmer_id && !blocked && (
                <Button
                  type="button"
                  variant="secondary"
                  leftIcon={<MapPinPlus className="h-4 w-4" />}
                  onClick={() => navigate(`/register/farmers/${existing.farmer_id}/fields/new`)}
                >
                  Add field directly
                </Button>
              )}
              <Button
                type="button"
                variant="secondary"
                onClick={() => leave('/register')}
                disabled={save.isPending}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                loading={save.isPending}
                disabled={blocked}
                leftIcon={<UserPlus className="h-4 w-4" />}
              >
                {editing || existing ? 'Save farmer & Open fields' : 'Register farmer'}
              </Button>
            </div>
          </div>
        </Card>

      </form>

      <ConfirmDialog
        open={leaving !== null}
        title="Leave without saving?"
        description="This farmer has not been saved. Everything entered will be lost."
        confirmLabel="Leave the form"
        cancelLabel="Keep editing"
        destructive
        onConfirm={() => {
          const to = leaving;
          setLeaving(null);
          if (to) navigate(to);
        }}
        onCancel={() => setLeaving(null)}
      />
    </PageContainer>
  );
}

/** Capitalise each word, leaving names with internal capitals alone (McDonald). */
function titleCase(value: string): string {
  return value
    .split(' ')
    .map((word) => {
      const core = word.replace(/['.-]/g, '');
      if (!core) return word;
      return core.toLowerCase() === core || core.toUpperCase() === core
        ? word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
        : word;
    })
    .join(' ');
}
