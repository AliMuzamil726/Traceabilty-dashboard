import { ImageOff, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { OFFICER_HEADER } from '@/core/api/client';
import { useOfficerStore } from '@/core/store/officerStore';
import { FileDropzone, IconButton, toast } from '@/design-system/components';
import type { Photo } from '../api/types';

export const MAX_PHOTOS = 8;
export const MAX_PHOTO_BYTES = 8 * 1024 * 1024;
const ACCEPT = 'image/jpeg,image/png,image/webp';

export interface PhotoUploaderProps {
  photos: Photo[];
  onUpload: (files: File[]) => void;
  onRemove: (photoId: string) => void;
  uploading?: boolean;
  readOnly?: boolean;
}

/**
 * Photos are fetched with the acting officer's header (not a bare <img src>), so the
 * route can require real authentication later without changing this screen.
 */
function Thumb({ photo }: { photo: Photo }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    const controller = new AbortController();
    const officer = useOfficerStore.getState().officerId;
    fetch(photo.thumb_url, { headers: officer ? { [OFFICER_HEADER]: officer } : {}, signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error('Photo unavailable');
        url = URL.createObjectURL(await res.blob());
        setSrc(url);
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) setFailed(true);
      });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [photo.thumb_url]);

  if (failed) return <ImageOff className="h-6 w-6 text-muted" aria-label="Photo unavailable" />;
  return src ? <img src={src} alt={photo.original_name} className="h-full w-full object-cover" /> : null;
}

export function PhotoUploader({ photos, onUpload, onRemove, uploading, readOnly }: PhotoUploaderProps) {
  const left = MAX_PHOTOS - photos.length;
  return (
    <div className="flex flex-col gap-3">
      {photos.length > 0 && (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {photos.map((photo) => (
            <li key={photo.id} className="relative flex aspect-square items-center justify-center overflow-hidden rounded-md border border-line bg-canvas">
              <Thumb photo={photo} />
              {!readOnly && (
                <span className="absolute right-1 top-1">
                  <IconButton label={`Remove ${photo.original_name}`} icon={<X className="h-4 w-4" />} size="sm" variant="secondary" onClick={() => onRemove(photo.id)} />
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {!readOnly && left > 0 && (
        <FileDropzone
          accept={ACCEPT}
          multiple
          maxSize={MAX_PHOTO_BYTES}
          disabled={uploading}
          label={uploading ? 'Uploading' : 'Add photos'}
          hint={`JPEG, PNG or WebP, 8 MB each. ${left} of ${MAX_PHOTOS} left.`}
          onReject={(file, reason) =>
            toast.error(`${file.name} was not added`, reason === 'too_large' ? 'It is larger than 8 MB.' : 'Use a JPEG, PNG or WebP image.')
          }
          onFiles={(files) => {
            if (files.length > left) toast.warning('Too many photos', `Only ${left} more can be added.`);
            if (files.length) onUpload(files.slice(0, left));
          }}
        />
      )}
      {readOnly && photos.length === 0 && <p className="text-sm text-muted">No photos.</p>}
    </div>
  );
}
