import type { ReactNode } from 'react';
import { Button } from './Button';
import { Dialog } from './Dialog';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Confirmation step. The confirm label names the action ("Delete field"), never "OK". */
export function ConfirmDialog({ open, title, description, confirmLabel, cancelLabel = 'Cancel', destructive, loading, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      description={description}
      size="sm"
      role="alertdialog"
      dismissible={!loading}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button variant={destructive ? 'danger' : 'primary'} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    />
  );
}
