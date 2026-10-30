import { CheckCircle2, MinusCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { useSites } from '@/core/hooks/useSharedData';
import { phoneInput } from '@/core/utils/validators';
import { Button, DatePicker, Dialog, FormField, Input, Textarea } from '@/design-system/components';
import type { Crop, Delivery, DeliveryDetail, InboxItem, Skipped } from '../api/types';
import { useSchedule, useTransition } from '../hooks/useTransition';
import { siteWord } from '../lib/variance';
import { todayIso, validateTransport, type TransportValues } from '../lib/validation';
import { SiteSelect } from './SiteSelect';

export interface ScheduleDialogProps {
  open: boolean;
  onClose: () => void;
  /** Schedule these requests (one delivery each, same transport). */
  requests?: InboxItem[];
  /** Or edit this scheduled delivery. */
  delivery?: DeliveryDetail;
  onDone?: () => void;
}

const EMPTY: TransportValues & { note: string } = { site_id: '', scheduled_date: '', driver_name: '', driver_phone: '', vehicle_no: '', note: '' };

export function ScheduleDialog({ open, onClose, requests = [], delivery, onDone }: ScheduleDialogProps) {
  const editing = Boolean(delivery);
  const crop: Crop | undefined = delivery?.crop ?? requests[0]?.crop;
  const sites = useSites(crop);
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<{ created: Delivery[]; skipped: Skipped[] } | null>(null);
  const schedule = useSchedule();
  const edit = useTransition(delivery?.id ?? '').update;

  useEffect(() => {
    if (!open) return;
    setErrors({});
    setResult(null);
    setValues(
      delivery
        ? { site_id: delivery.site?.id ?? '', scheduled_date: delivery.scheduled_date, driver_name: delivery.driver_name,
            driver_phone: delivery.driver_phone, vehicle_no: delivery.vehicle_no, note: delivery.note ?? '' }
        : { ...EMPTY, scheduled_date: todayIso() },
    );
  }, [open, delivery]);

  const country = sites.data?.find((s) => s.id === values.site_id)?.country;
  const set = (key: keyof typeof values) => (value: string) => setValues((v) => ({ ...v, [key]: value }));
  const word = crop ? siteWord(crop).site : 'Site';

  const submit = () => {
    const found = validateTransport(values, country, todayIso());
    setErrors(found);
    if (Object.keys(found).length) return;
    const body = { ...values, vehicle_no: values.vehicle_no.trim().toUpperCase(), note: values.note.trim() || null };
    const onError = (e: unknown) => {
      const err = toApiError(e);
      setErrors(Object.keys(err.fieldErrors).length ? err.fieldErrors : { form: err.message });
    };
    if (editing) {
      edit.mutate(body, { onSuccess: () => { onDone?.(); onClose(); }, onError });
    } else {
      schedule.mutate(
        { ...body, request_ids: requests.map((r) => r.request_id) },
        { onSuccess: (r) => { setResult(r); onDone?.(); }, onError },
      );
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={result ? 'Deliveries scheduled' : editing ? `Edit ${delivery?.delivery_no}` : `Schedule ${requests.length} ${requests.length === 1 ? 'delivery' : 'deliveries'}`}
      description={result || editing ? undefined : 'The same transport details apply to every selected request; each gets its own delivery.'}
      footer={
        result ? (
          <Button onClick={onClose}>Done</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button loading={schedule.isPending || edit.isPending} onClick={submit}>{editing ? 'Save changes' : 'Schedule'}</Button>
          </>
        )
      }
    >
      {result ? (
        <div className="flex flex-col gap-3" aria-live="polite">
          <ul className="flex flex-col gap-1">
            {result.created.map((d) => (
              <li key={d.id} className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="h-4 w-4 text-forest-700" aria-hidden />
                <span className="font-mono">{d.delivery_no}</span> field {d.field_code}
              </li>
            ))}
            {result.skipped.map((s) => (
              <li key={s.pickup_request_id} className="flex items-start gap-2 text-sm">
                <MinusCircle className="mt-0.5 h-4 w-4 text-wheat-600" aria-hidden />
                <span><span className="font-mono">{s.field_code ?? s.pickup_request_id}</span>: <span className="text-muted">{s.reason}</span></span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormField label={word} required error={errors.site_id} className="sm:col-span-2">
            <SiteSelect crop={crop} value={values.site_id} onChange={set('site_id')} invalid={Boolean(errors.site_id)} />
          </FormField>
          <FormField label="Scheduled date" required error={errors.scheduled_date}>
            <DatePicker value={values.scheduled_date || null} min={todayIso()} onValueChange={(v) => set('scheduled_date')(v ?? '')} />
          </FormField>
          <FormField label="Vehicle number" required error={errors.vehicle_no}>
            <Input value={values.vehicle_no} maxLength={20} className="uppercase" onChange={(e) => set('vehicle_no')(e.target.value)} />
          </FormField>
          <FormField label="Driver name" required error={errors.driver_name}>
            <Input value={values.driver_name} maxLength={120} onChange={(e) => set('driver_name')(e.target.value)} />
          </FormField>
          <FormField label="Driver phone" required error={errors.driver_phone} hint={country === 'GB' ? 'UK mobile, for example 07700 900123.' : country === 'PK' ? 'Pakistani mobile, for example 0300 1234567.' : undefined}>
            <Input type="tel" inputMode="tel" value={values.driver_phone} maxLength={16} onChange={(e) => set('driver_phone')(phoneInput(e.target.value))} />
          </FormField>
          <FormField label="Note" className="sm:col-span-2" hint="Optional.">
            <Textarea rows={2} maxLength={1000} value={values.note} onChange={(e) => set('note')(e.target.value)} />
          </FormField>
          {errors.form && <p role="alert" className="text-sm text-danger sm:col-span-2">{errors.form}</p>}
        </div>
      )}
    </Dialog>
  );
}
