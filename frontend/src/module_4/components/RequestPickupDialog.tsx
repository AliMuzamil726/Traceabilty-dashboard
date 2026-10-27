import { CheckCircle2, MinusCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { formatDecimal, formatNumber } from '@/core/utils/format';
import { Button, DatePicker, Dialog, FormField, KeyValueList, Textarea } from '@/design-system/components';
import type { Crop, PickupResult, RadarRow } from '../api/types';
import { useRequestPickup } from '../hooks/useRequestPickup';
import { areaOf } from '../lib/selection';

export interface RequestPickupDialogProps {
  open: boolean;
  rows: RadarRow[];
  crop: Crop;
  season: number;
  unit: 'acre' | 'ha';
  onClose: () => void;
  onDone: () => void;
}

/** Summary, optional date and note, then the result: created requests and skipped fields. */
export function RequestPickupDialog({ open, rows, crop, season, unit, onClose, onDone }: RequestPickupDialogProps) {
  const [date, setDate] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const [result, setResult] = useState<PickupResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mutation = useRequestPickup();

  useEffect(() => {
    if (open) {
      setDate(null);
      setNote('');
      setResult(null);
      setError(null);
    }
  }, [open]);

  const area = rows.reduce((sum, r) => sum + areaOf(r, unit), 0);
  const kg = rows.reduce((sum, r) => sum + (r.estimated_kg ?? 0), 0);
  const anyEstimate = rows.some((r) => r.estimate_is_benchmark);
  const today = new Date().toISOString().slice(0, 10);

  const confirm = () => {
    setError(null);
    mutation.mutate(
      { crop, season_year: season, field_ids: rows.map((r) => r.field_id), preferred_date: date, note: note.trim() || null },
      {
        onSuccess: (data) => {
          setResult(data);
          onDone();
        },
        onError: (e) => setError(toApiError(e).message),
      },
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={result ? 'Pickup requests' : 'Request pickup'}
      description={result ? undefined : 'The logistics team picks these up in Deliveries.'}
      footer={
        result ? (
          <Button onClick={onClose}>Done</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button loading={mutation.isPending} onClick={confirm}>
              Confirm request
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div className="flex flex-col gap-4" aria-live="polite">
          {result.created.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-ink">Requested ({result.created.length})</h3>
              <ul className="mt-2 flex flex-col gap-1">
                {result.created.map((r) => (
                  <li key={r.id} className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="h-4 w-4 text-forest-700" aria-hidden />
                    <span className="font-mono">{r.request_no}</span>
                    <span>field {r.field_code}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.skipped.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-ink">Skipped ({result.skipped.length})</h3>
              <ul className="mt-2 flex flex-col gap-1">
                {result.skipped.map((s) => (
                  <li key={s.field_id} className="flex items-start gap-2 text-sm">
                    <MinusCircle className="mt-0.5 h-4 w-4 shrink-0 text-wheat-600" aria-hidden />
                    <span>
                      <span className="font-mono">{s.field_code ?? s.field_id}</span>: <span className="text-muted">{s.reason}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <KeyValueList
            columns={2}
            items={[
              { label: 'Fields', value: formatNumber(rows.length) },
              { label: 'Total area', value: `${formatDecimal(area)} ${unit === 'acre' ? 'acres' : 'ha'}` },
              { label: anyEstimate ? 'Estimated quantity (includes benchmarks)' : 'Estimated quantity', value: `${formatNumber(kg)} kg` },
              { label: 'Season', value: String(season) },
            ]}
          />
          <FormField label="Preferred pickup date" hint="Optional.">
            <DatePicker value={date} min={today} onValueChange={setDate} />
          </FormField>
          <FormField label="Note for logistics" hint="Optional. Access, contact or timing details.">
            <Textarea value={note} maxLength={1000} rows={3} onChange={(e) => setNote(e.target.value)} />
          </FormField>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
        </div>
      )}
    </Dialog>
  );
}
