import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toApiError } from '@/core/api/errors';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { Button, Dialog, FormField, NumberInput, Skeleton } from '@/design-system/components';
import { fieldbookApi, fieldbookKeys } from '../api/client';
import type { FarmerOption } from '../api/types';
import { FarmerCombobox } from './FarmerCombobox';
import { farmerLabel } from '../lib/display';
import { FieldCards } from './FieldCards';
import { OfficerSelect } from './OfficerSelect';
import { bookPath } from '../lib/display';

export interface SelectionDialogProps {
  open: boolean;
  onClose: () => void;
  /** Deep link: preselect this farmer (and field). */
  initialFarmerId?: string | null;
  initialFieldId?: string | null;
}

/** Officer, then farmer, then field, then season: opens (or creates) the fieldbook. */
export function SelectionDialog({ open, onClose, initialFarmerId, initialFieldId }: SelectionDialogProps) {
  const navigate = useNavigate();
  const me = useCurrentOfficer();
  const [officerId, setOfficerId] = useState<string | null>(null);
  const [farmer, setFarmer] = useState<Pick<FarmerOption, 'id' | 'sawie_id' | 'name'> | null>(null);
  const [fieldId, setFieldId] = useState<string | null>(initialFieldId ?? null);
  const [season, setSeason] = useState<number>(new Date().getFullYear());
  const [error, setError] = useState<string | null>(null);

  const officers = useQuery({
    queryKey: fieldbookKeys.officers,
    queryFn: ({ signal }) => fieldbookApi.officers(signal),
    enabled: open,
  });

  // Default to the acting officer when listed, otherwise the first officer offered.
  useEffect(() => {
    if (officerId || !officers.data?.length) return;
    const self = officers.data.find((o) => o.id === me.data?.id);
    setOfficerId((self ?? officers.data[0])?.id ?? null);
  }, [officers.data, me.data, officerId]);

  const farmerId = farmer?.id ?? initialFarmerId ?? null;
  const fields = useQuery({
    queryKey: fieldbookKeys.fields(farmerId, season),
    queryFn: ({ signal }) => fieldbookApi.fields(farmerId as string, season, signal),
    enabled: open && Boolean(farmerId),
  });

  // A deep link names the farmer by id; take its name from the field selector's answer.
  useEffect(() => {
    if (!farmer && fields.data && fields.data.farmer.id === initialFarmerId) {
      setFarmer({ id: fields.data.farmer.id, sawie_id: fields.data.farmer.sawie_id, name: fields.data.farmer.name });
    }
  }, [fields.data, farmer, initialFarmerId]);

  // One field: choose it for the officer.
  useEffect(() => {
    const items = fields.data?.items ?? [];
    if (items.length === 1 && !fieldId) setFieldId(items[0]!.id);
    if (fieldId && items.length && !items.some((f) => f.id === fieldId)) setFieldId(null);
  }, [fields.data, fieldId]);

  const openBook = useMutation({
    mutationFn: () => fieldbookApi.open(fieldId as string, season),
    onSuccess: (book) => {
      onClose();
      navigate(bookPath(book.id, book.locked));
    },
    onError: (e) => setError(toApiError(e).message),
  });

  const fieldsError = fields.error ? toApiError(fields.error).message : null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Open a fieldbook"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            rightIcon={<ArrowRight className="h-4 w-4" />}
            disabled={!fieldId || !season}
            loading={openBook.isPending}
            onClick={() => {
              setError(null);
              openBook.mutate();
            }}
          >
            Open fieldbook
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {me.data?.role !== 'officer' && (
        <FormField label="Officer">
          <OfficerSelect
            officers={officers.data ?? []}
            value={officerId}
            loading={officers.isLoading}
            onChange={(id) => {
              setOfficerId(id);
              setFarmer(null);
              setFieldId(null);
            }}
          />
        </FormField>
        )}

        <FormField label="Farmer" required>
          <FarmerCombobox
            officerId={officerId}
            seasonYear={season}
            value={farmer?.id ?? null}
            selectedLabel={farmer ? farmerLabel(farmer) : undefined}
            onChange={(f) => {
              setFarmer(f);
              setFieldId(null);
              setError(null);
            }}
          />
        </FormField>

        {farmerId && (
          <FormField label="Field" required error={fieldsError}>
            {fields.isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : fields.data ? (
              <FieldCards
                farmerId={farmerId}
                crop={fields.data.farmer.crop}
                fields={fields.data.items}
                value={fieldId}
                onChange={setFieldId}
              />
            ) : (
              <span />
            )}
          </FormField>
        )}

        <FormField label="Season" required className="max-w-[12rem]">
          <NumberInput value={season} onValueChange={(v) => setSeason(v ?? new Date().getFullYear())} decimals={0} min={2000} max={2100} />
        </FormField>

        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </Dialog>
  );
}
