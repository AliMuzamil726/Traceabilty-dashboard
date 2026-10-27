import Cropper from 'react-easy-crop';
import type { Area } from 'react-easy-crop';
import { useCallback, useState } from 'react';
import { Button } from '@/design-system/components/Button';
import { Dialog } from '@/design-system/components/Dialog';

export interface PhotoCropDialogProps {
  /** The object-URL of the image selected by the user. */
  imageSrc: string | null;
  open: boolean;
  onClose: () => void;
  /** Called with the cropped Blob when the user confirms. */
  onCropped: (blob: Blob) => void;
  loading?: boolean;
}

/** Extracts the cropped region from a source image and returns a Blob. */
async function getCroppedBlob(src: string, crop: Area): Promise<Blob> {
  const image = new Image();
  image.crossOrigin = 'anonymous';
  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = reject;
    image.src = src;
  });

  const canvas = document.createElement('canvas');
  const size = Math.min(crop.width, crop.height);
  // Output a 512x512 image for consistency
  const outputSize = 512;
  canvas.width = outputSize;
  canvas.height = outputSize;

  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(image, crop.x, crop.y, size, size, 0, 0, outputSize, outputSize);

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Canvas is empty'))),
      'image/jpeg',
      0.92,
    );
  });
}

export function PhotoCropDialog({ imageSrc, open, onClose, onCropped, loading }: PhotoCropDialogProps) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedArea, setCroppedArea] = useState<Area | null>(null);

  const onCropComplete = useCallback((_: Area, croppedPixels: Area) => {
    setCroppedArea(croppedPixels);
  }, []);

  const handleConfirm = async () => {
    if (!imageSrc || !croppedArea) return;
    const blob = await getCroppedBlob(imageSrc, croppedArea);
    onCropped(blob);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Crop profile photo"
      size="md"
      dismissible={!loading}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} loading={loading}>
            Upload
          </Button>
        </div>
      }
    >
      <div className="relative mx-auto h-[320px] w-full overflow-hidden rounded-card bg-forest-950">
        {imageSrc && (
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            aspect={1}
            cropShape="round"
            showGrid={false}
            onCropChange={setCrop}
            onZoomChange={setZoom}
            onCropComplete={onCropComplete}
          />
        )}
      </div>
      <div className="mt-3 flex items-center gap-3 px-1">
        <span className="text-xs text-muted">Zoom</span>
        <input
          type="range"
          min={1}
          max={3}
          step={0.05}
          value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))}
          className="h-1.5 flex-1 cursor-pointer appearance-none rounded-pill bg-forest-100 accent-forest-700 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-forest-700"
        />
      </div>
    </Dialog>
  );
}
