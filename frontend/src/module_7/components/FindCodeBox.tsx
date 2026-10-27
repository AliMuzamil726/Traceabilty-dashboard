import { Camera, Search } from 'lucide-react';
import { useCallback, useState, type FormEvent } from 'react';
import { toApiError } from '@/core/api/errors';
import { Button, FormField, Input } from '@/design-system/components';
import type { Resolved } from '../api/types';
import { useResolve } from '../hooks/useTrace';
import { classifyCode } from '../lib/codes';
import { CameraScanner } from './CameraScanner';

/** Find a bale or lot from a code, a bale serial or a trace link, typed, pasted or scanned. */
export function FindCodeBox({ onFound }: { onFound: (r: Resolved) => void }) {
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const resolve = useResolve();

  const run = useCallback((raw: string) => {
    const input = classifyCode(raw);
    if (input.kind === 'empty') { setError('Enter a code, a bale serial or a trace link.'); return; }
    setError(null);
    // A link is reduced to its code first; the server checks either way.
    resolve.mutate(input.kind === 'serial' ? input.text : input.token, {
      onSuccess: (r) => { onFound(r); },
      onError: (e) => setError(toApiError(e).message),
    });
  }, [resolve, onFound]);

  const onScan = useCallback((value: string) => { setScanning(false); setText(value); run(value); }, [run]);

  return (
    <form aria-label="Code search" className="flex flex-wrap items-end gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); run(text); }}>
      <div className="min-w-[260px] flex-1">
        <FormField label="Find a code" error={error} hint={error ? undefined : 'A code, a bale serial or a trace link.'}>
          <Input mono value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. BWP-G1-H01-001" />
        </FormField>
      </div>
      <Button type="submit" loading={resolve.isPending} leftIcon={<Search className="h-4 w-4" />}>Find</Button>
      <Button type="button" variant="secondary" leftIcon={<Camera className="h-4 w-4" />} onClick={() => setScanning(true)}>Scan</Button>
      <CameraScanner open={scanning} onClose={() => setScanning(false)} onResult={onScan} />
    </form>
  );
}
