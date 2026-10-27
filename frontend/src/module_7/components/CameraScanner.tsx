import { CameraOff } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Button, Dialog } from '@/design-system/components';

interface DetectedBarcode { rawValue: string }
interface BarcodeDetectorLike { detect(source: HTMLVideoElement): Promise<DetectedBarcode[]> }
type DetectorCtor = new (options: { formats: string[] }) => BarcodeDetectorLike;

function detectorClass(): DetectorCtor | null {
  const ctor = (globalThis as { BarcodeDetector?: DetectorCtor }).BarcodeDetector;
  return typeof ctor === 'function' ? ctor : null;
}

/** Camera scanning with the browser's BarcodeDetector. Where it is missing, says so and suggests typing. */
export function CameraScanner({ open, onClose, onResult }: { open: boolean; onClose: () => void; onResult: (text: string) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    const Detector = detectorClass();
    if (!Detector || !navigator.mediaDevices?.getUserMedia) {
      setProblem('This browser cannot scan codes with the camera. Type or paste the code instead, or use the phone camera app to open the link.');
      return undefined;
    }
    setProblem(null);
    let stream: MediaStream | null = null;
    let timer: number | undefined;
    let live = true;
    const detector = new Detector({ formats: ['qr_code'] });
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }).then((s) => {
      stream = s;
      if (!live || !video.current) return;
      video.current.srcObject = s;
      void video.current.play();
      const tick = async () => {
        if (!live || !video.current) return;
        try {
          const found = await detector.detect(video.current);
          if (found[0]?.rawValue) { onResult(found[0].rawValue); return; }
        } catch { /* a frame that is not ready yet */ }
        timer = window.setTimeout(() => void tick(), 300);
      };
      void tick();
    }).catch(() => setProblem('The camera could not be opened. Allow camera access, or type the code instead.'));
    return () => {
      live = false;
      window.clearTimeout(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [open, onResult]);

  return (
    <Dialog open={open} onClose={onClose} title="Scan a code" footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      {problem ? (
        <div role="status" className="flex items-start gap-2 text-sm text-ink">
          <CameraOff aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <p>{problem}</p>
        </div>
      ) : (
        <video ref={video} muted playsInline aria-label="Camera preview" className="aspect-square w-full rounded-card bg-forest-950 object-cover" />
      )}
    </Dialog>
  );
}
