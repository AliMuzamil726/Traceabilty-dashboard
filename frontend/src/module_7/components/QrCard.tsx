import { Copy, Download, ExternalLink } from 'lucide-react';
import { toApiError } from '@/core/api/errors';
import { Button, Skeleton, toast } from '@/design-system/components';
import { qrApi } from '../api/client';
import { useQrImage } from '../hooks/useLots';
import { copyText, download } from '../lib/download';

export interface QrCardProps {
  token: string;
  url: string;
  /** Used for file names and the image description. */
  name: string;
}

/** A QR code with Copy link and PNG or SVG downloads. */
export function QrCard({ token, url, name }: QrCardProps) {
  const src = useQrImage(token, 8);
  const save = (kind: 'png' | 'svg') =>
    download(kind === 'png' ? qrApi.pngPath(token, 16) : qrApi.svgPath(token), `${name}.${kind}`)
      .catch((e: unknown) => toast.error('The download failed', toApiError(e).message));
  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
      <div className="flex h-44 w-44 shrink-0 items-center justify-center rounded-card border border-line bg-white p-1">
        {src ? <img src={src} alt={`QR code for ${name}`} className="h-full w-full [image-rendering:pixelated]" /> : <Skeleton className="h-40 w-40" shape="block" />}
      </div>
      <div className="flex min-w-0 flex-col gap-2">
        <p className="text-xs text-muted">Trace link</p>
        <a href={url} target="_blank" rel="noreferrer" className="mono-id break-all text-sm text-forest-700 underline-offset-2 hover:underline">
          {url}<ExternalLink aria-hidden className="ml-1 inline h-3.5 w-3.5" />
        </a>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" leftIcon={<Copy className="h-4 w-4" />}
            onClick={() => void copyText(url).then((ok) => (ok ? toast.success('Link copied') : toast.error('Copy failed', url)))}>
            Copy link
          </Button>
          <Button size="sm" variant="ghost" leftIcon={<Download className="h-4 w-4" />} onClick={() => void save('png')}>PNG</Button>
          <Button size="sm" variant="ghost" leftIcon={<Download className="h-4 w-4" />} onClick={() => void save('svg')}>SVG</Button>
        </div>
      </div>
    </div>
  );
}
