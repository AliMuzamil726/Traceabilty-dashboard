import { FileDown } from 'lucide-react';
import { useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { Button, Dialog, toast } from '@/design-system/components';
import { qrApi } from '../api/client';
import { download } from '../lib/download';

export interface LabelPrintDialogProps {
  open: boolean;
  onClose: () => void;
  serials: string[];
  onPrinted: () => void;
}

/** A4 sheets, 3 by 8 labels: QR, serial, lot, site, production date and "Scan to trace". */
export function LabelPrintDialog({ open, onClose, serials, onPrinted }: LabelPrintDialogProps) {
  const [busy, setBusy] = useState(false);
  const pages = Math.max(1, Math.ceil(serials.length / 24));
  const run = async () => {
    setBusy(true);
    try {
      await download(qrApi.labelsPath, 'labels.pdf', { serials });
      toast.success(`${serials.length} ${serials.length === 1 ? 'label' : 'labels'} ready`);
      onPrinted();
      onClose();
    } catch (e) {
      toast.error('The labels could not be made', toApiError(e).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onClose={onClose} dismissible={!busy} title="Print labels"
      description={`${serials.length} ${serials.length === 1 ? 'label' : 'labels'} on ${pages} A4 ${pages === 1 ? 'page' : 'pages'}, 24 to a page.`}
      footer={<>
        <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button loading={busy} leftIcon={<FileDown className="h-4 w-4" />} onClick={() => void run()}>Download PDF</Button>
      </>}>
      <p className="text-sm text-muted">Each print is counted against the bale&apos;s code and recorded in the audit log. Print at 100% scale.</p>
    </Dialog>
  );
}
