import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { cn } from '@/core/utils/cn';
import { Button, Dialog, FormField, NumberInput, Textarea, toast } from '@/design-system/components';
import type { GateEntry } from '../api/types';
import { useGateActions } from '../hooks/useGate';
import {
  LEVEL_CLASSES,
  LEVEL_LABEL,
  kgText,
  netWeight,
  previewVariance,
  referenceWeight,
  validateAccept,
} from '../lib/gate';

/** Weighbridge reading and moisture for a load at the gate, with the variance shown first. */
export function AcceptDialog({ entry, open, onClose }: { entry: GateEntry; open: boolean; onClose: () => void }) {
  const [gross, setGross] = useState<number | null>(null);
  const [tare, setTare] = useState<number | null>(null);
  const [moisture, setMoisture] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const { accept } = useGateActions();
  useEffect(() => {
    if (!open) return;
    setGross(null);
    setTare(null);
    setMoisture(null);
    setNote('');
    setErrors({});
  }, [open, entry.id]);

  const net = netWeight(gross, tare);
  const variance = previewVariance(net, entry);
  const reference = referenceWeight(entry);
  const needsNote = variance?.level === 'flag';
  const warnPct = entry.moisture_warn_pct;
  const moistureHigh = moisture !== null && warnPct !== null && moisture > warnPct;

  const confirm = () => {
    const found = validateAccept({ gross, tare, moisture, note }, entry);
    setErrors(found);
    if (Object.keys(found).length || gross === null || tare === null || moisture === null) return;
    accept.mutate(
      {
        entryId: entry.id,
        body: { gross_weight_kg: gross, tare_weight_kg: tare, moisture_pct: moisture, note: note.trim() || null },
      },
      {
        onSuccess: (result) => {
          toast.success(`${entry.delivery_no} received`, result.warnings.join(' ') || `Net ${kgText(net, entry.crop)}.`);
          onClose();
        },
        onError: (e) => {
          const err = toApiError(e);
          setErrors({ ...err.fieldErrors, form: err.message });
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Weigh and accept ${entry.delivery_no}`}
      description={`${entry.vehicle_no} · ${entry.driver_name}`}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={accept.isPending} onClick={confirm}>Accept load</Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormField
          label="Gross weight"
          required
          error={errors.gross_weight_kg}
          hint="Truck and load on the weighbridge."
        >
          <NumberInput value={gross} onValueChange={setGross} unit="kg" min={0} decimals={1} />
        </FormField>
        <FormField
          label="Tare weight"
          required
          error={errors.tare_weight_kg}
          hint="Empty truck, from its earlier ticket."
        >
          <NumberInput value={tare} onValueChange={setTare} unit="kg" min={0} decimals={1} />
        </FormField>
        <FormField label="Net weight" hint="Gross minus tare. This is what the delivery records.">
          <div data-testid="net-weight" className="flex min-h-10 items-center text-base font-semibold tabular-nums text-ink">
            {net !== null && net > 0 ? kgText(net, entry.crop) : '-'}
          </div>
        </FormField>
        <FormField
          label="Moisture"
          required
          error={errors.moisture_pct}
          hint={
            moistureHigh ? (
              <span className="text-wheat-600">Above the {warnPct}% limit for {entry.crop}.</span>
            ) : warnPct !== null ? (
              `Limit ${warnPct}%`
            ) : undefined
          }
        >
          <NumberInput value={moisture} onValueChange={setMoisture} unit="%" min={0} max={100} decimals={1} />
        </FormField>
        <div className="rounded-control border border-line bg-canvas p-3 sm:col-span-2" aria-live="polite" data-testid="variance-preview">
          {!reference ? (
            <p className="text-sm text-muted">No field weight or estimate to compare with.</p>
          ) : variance ? (
            <p className={cn('text-sm font-medium', LEVEL_CLASSES[variance.level])}>
              Variance {variance.varianceKg > 0 ? '+' : ''}
              {variance.varianceKg} kg ({variance.variancePct}%) against the {variance.referenceLabel} of{' '}
              {variance.referenceKg.toLocaleString('en-GB')} kg: {LEVEL_LABEL[variance.level]}.
            </p>
          ) : (
            <p className="text-sm text-muted">Enter the gross and tare weights to see the variance.</p>
          )}
          {entry.variance_warn_pct !== null && entry.variance_flag_pct !== null && (
            <p className="mt-1 text-xs text-muted">
              Check at {entry.variance_warn_pct}%, flag at {entry.variance_flag_pct}%.
            </p>
          )}
        </div>
        <FormField
          label="Note"
          required={needsNote}
          error={errors.note}
          className="sm:col-span-2"
          hint={needsNote ? 'Explain the weight difference before accepting.' : 'Optional.'}
        >
          <Textarea rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
        </FormField>
        {errors.form && <p role="alert" className="text-sm text-danger sm:col-span-2">{errors.form}</p>}
      </div>
    </Dialog>
  );
}
