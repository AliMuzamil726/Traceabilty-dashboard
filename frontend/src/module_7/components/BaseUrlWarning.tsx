import { TriangleAlert } from 'lucide-react';
import { isLocalBaseUrl } from '../lib/codes';

/** Shown when printed codes would point at this computer only, so phones could not open them. */
export function BaseUrlWarning({ baseUrl }: { baseUrl: string | null | undefined }) {
  if (!isLocalBaseUrl(baseUrl)) return null;
  return (
    <div role="alert" className="flex items-start gap-3 rounded-card border border-wheat-300 bg-wheat-50 p-3 text-sm text-ink">
      <TriangleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-wheat-600" />
      <div>
        <p className="font-medium">Phones cannot open these codes yet</p>
        <p className="mt-0.5 text-muted">
          Codes point at <span className="mono-id">{baseUrl}</span>, which only works on this computer. Set{' '}
          <span className="mono-id">PUBLIC_BASE_URL</span> in <span className="mono-id">backend/.env</span> to this computer&apos;s
          network address (for example <span className="mono-id">http://192.168.1.20:5173</span>), restart, and print again.
        </p>
      </div>
    </div>
  );
}
