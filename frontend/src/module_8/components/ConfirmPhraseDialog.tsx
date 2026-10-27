import { useEffect, useState } from 'react';
import { Button } from '@/design-system/components/Button';
import { Dialog } from '@/design-system/components/Dialog';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';

export interface ConfirmPhraseDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description: React.ReactNode;
  /** The word that has to be typed exactly, e.g. RESTORE. */
  phrase: string;
  confirmLabel: string;
  loading?: boolean;
  onConfirm: () => void;
}

/**
 * The confirmation for something that cannot be undone.
 *
 * A typed phrase rather than a second button, because the actions behind it (replacing
 * the database) destroy work, and a button is too easy to click twice.
 */
export function ConfirmPhraseDialog({
  open,
  onClose,
  title,
  description,
  phrase,
  confirmLabel,
  loading,
  onConfirm,
}: ConfirmPhraseDialogProps) {
  const [typed, setTyped] = useState('');
  useEffect(() => {
    if (!open) setTyped('');
  }, [open]);

  const matches = typed.trim() === phrase;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      role="alertdialog"
      size="sm"
      dismissible={!loading}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={!matches} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="text-base text-ink">{description}</div>
        <FormField label={`Type ${phrase} to confirm`}>
          <Input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            autoComplete="off"
            spellCheck={false}
            mono
          />
        </FormField>
      </div>
    </Dialog>
  );
}
