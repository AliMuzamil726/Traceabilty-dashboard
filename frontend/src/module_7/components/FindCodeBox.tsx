import { Camera, Search } from 'lucide-react';
import { useCallback, useState, type FormEvent } from 'react';
import { toApiError } from '@/core/api/errors';
import { cn } from '@/core/utils/cn';
import { Button, Input } from '@/design-system/components';
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

  // The label and hint sit outside the row so the buttons share the input's line.
  return (
    <form aria-label="Code search" className="flex flex-col gap-1.5" onSubmit={(e: FormEvent) => { e.preventDefault(); run(text); }}>
      <label htmlFor="find-code" className="text-sm font-medium leading-snug text-ink">Find a code</label>
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-[260px] flex-1">
          <Input
            id="find-code"
            mono
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. BWP-G1-H01-001"
            invalid={Boolean(error)}
            aria-describedby="find-code-hint"
          />
        </div>
        <Button type="submit" loading={resolve.isPending} leftIcon={<Search className="h-4 w-4" />}>Find</Button>
        <Button type="button" variant="secondary" leftIcon={<Camera className="h-4 w-4" />} onClick={() => setScanning(true)}>Scan</Button>
      </div>
      <p id="find-code-hint" role={error ? 'alert' : undefined} className={cn('text-sm', error ? 'text-danger' : 'text-muted')}>
        {error ?? 'A code, a bale serial or a trace link.'}
      </p>
      <CameraScanner open={scanning} onClose={() => setScanning(false)} onResult={onScan} />
    </form>
  );
}
