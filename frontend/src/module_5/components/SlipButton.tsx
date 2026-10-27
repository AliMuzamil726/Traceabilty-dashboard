import { FileDown } from 'lucide-react';
import { useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { Button, toast } from '@/design-system/components';
import { deliveriesApi } from '../api/client';

/** One-page PDF for the driver, with a QR of the delivery number. */
export function SlipButton({ deliveryId }: { deliveryId: string }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button size="sm" variant="secondary" leftIcon={<FileDown className="h-4 w-4" />} loading={busy}
      onClick={() => {
        setBusy(true);
        deliveriesApi.download(`/${deliveryId}/slip.pdf`)
          .catch((e: unknown) => toast.error('The slip was not downloaded', toApiError(e).message))
          .finally(() => setBusy(false));
      }}>
      Download slip
    </Button>
  );
}
