import { AlertTriangle, CheckCircle2, Upload } from 'lucide-react';
import { useState } from 'react';
import { ApiError } from '@/core/api/errors';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Dialog } from '@/design-system/components/Dialog';
import { FileDropzone } from '@/design-system/components/FileDropzone';
import type { ImportReport } from '../api/types';

export interface CsvImportDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  /** The columns the file must have, shown before anything is uploaded. */
  columns: string[];
  /** Runs the import. `dryRun` true must change nothing on the server. */
  onImport: (text: string, dryRun: boolean) => Promise<ImportReport>;
  onDone?: () => void;
}

/**
 * Import a CSV, with the check run first.
 *
 * Nothing is written until the file has been read back as a list of what would happen,
 * so a wrong column or a typo in a code is found before it reaches the database rather
 * than after.
 */
export function CsvImportDialog({
  open,
  onClose,
  title,
  columns,
  onImport,
  onDone,
}: CsvImportDialogProps) {
  const [text, setText] = useState<string | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [committed, setCommitted] = useState(false);

  const reset = () => {
    setText(null);
    setReport(null);
    setFailure(null);
    setCommitted(false);
  };

  const run = async (dryRun: boolean) => {
    if (!text) return;
    setBusy(true);
    setFailure(null);
    try {
      const result = await onImport(text, dryRun);
      setReport(result);
      if (!dryRun) {
        setCommitted(true);
        onDone?.();
      }
    } catch (error) {
      setFailure(error instanceof ApiError ? error.message : 'The file could not be read.');
    } finally {
      setBusy(false);
    }
  };

  const errors = report?.errors ?? [];
  const canCommit = report !== null && errors.length === 0 && !committed;

  return (
    <Dialog
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title={title}
      size="lg"
      dismissible={!busy}
      footer={
        <>
          <Button
            variant="secondary"
            onClick={() => {
              reset();
              onClose();
            }}
            disabled={busy}
          >
            {committed ? 'Close' : 'Cancel'}
          </Button>
          {!committed && (
            <Button onClick={() => void run(!report || errors.length > 0)} loading={busy} disabled={!text}>
              {canCommit ? 'Import these rows' : 'Check the file'}
            </Button>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          The file needs these columns: <span className="mono-id">{columns.join(', ')}</span>. The
          first row is the heading row.
        </p>

        <FileDropzone
          accept=".csv,text/csv"
          onFiles={(files) => {
            const file = files[0];
            if (!file) return;
            void file.text().then((content) => {
              setText(content);
              setReport(null);
              setCommitted(false);
            });
          }}
        />

        {failure && (
          <p className="rounded-control bg-danger-tint px-3 py-2 text-sm text-danger">{failure}</p>
        )}

        {report && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="success">{report.created} to add</Badge>
              <Badge tone="info">{report.updated} to change</Badge>
              <Badge tone="neutral">{report.skipped} unchanged</Badge>
              {errors.length > 0 && <Badge tone="danger">{errors.length} with a problem</Badge>}
            </div>

            {committed ? (
              <p className="flex items-center gap-2 text-base text-forest-800">
                <CheckCircle2 className="h-4 w-4" aria-hidden />
                Imported.
              </p>
            ) : errors.length > 0 ? (
              <div>
                <p className="flex items-center gap-2 text-sm font-medium text-danger">
                  <AlertTriangle className="h-4 w-4" aria-hidden />
                  Fix these rows in the file, then try again. Nothing has been saved.
                </p>
                <ul className="mt-2 flex max-h-56 flex-col gap-1 overflow-auto text-sm">
                  {errors.map((error, index) => (
                    <li key={index} className="rounded-sm bg-danger-tint px-2 py-1 text-ink">
                      {typeof error.row === 'number' ? `Row ${error.row}: ` : ''}
                      {String(error.message ?? JSON.stringify(error))}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="flex items-center gap-2 text-sm text-muted">
                <Upload className="h-4 w-4" aria-hidden />
                Nothing has been saved yet. Choose Import to apply these rows.
              </p>
            )}
          </div>
        )}
      </div>
    </Dialog>
  );
}
