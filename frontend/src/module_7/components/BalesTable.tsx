import { Archive, Copy, Printer, RefreshCw, Search, ShieldOff } from 'lucide-react';
import { useState } from 'react';
import { toApiError } from '@/core/api/errors';
import { formatDateTime } from '@/core/utils/format';
import { Badge, Button, DataTable, Dialog, EmptyState, FormField, IconButton, Textarea, toast, type Column } from '@/design-system/components';
import { qrApi } from '../api/client';
import type { BaleRow } from '../api/types';
import { useQrActions } from '../hooks/useLots';
import { copyText, download } from '../lib/download';
import { LabelPrintDialog } from './LabelPrintDialog';

type AdminAction = { kind: 'revoke' | 'regenerate'; row: BaleRow };

export interface BalesTableProps {
  heapId: string;
  rows: BaleRow[];
  loading: boolean;
  isAdmin: boolean;
  onTrace: (serial: string) => void;
}

function codeBadge(r: BaleRow) {
  if (r.bale_status === 'voided') return <Badge size="sm">Bale voided</Badge>;
  if (r.token_status === 'active') return <Badge size="sm" tone="success">Active</Badge>;
  if (r.token_status === 'revoked') return <Badge size="sm" tone="warning">Revoked</Badge>;
  return <Badge size="sm">No code</Badge>;
}

export function BalesTable({ heapId, rows, loading, isAdmin, onTrace }: BalesTableProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [printing, setPrinting] = useState(false);
  const [action, setAction] = useState<AdminAction | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { revoke, regenerate, refresh } = useQrActions();
  const printable = rows.filter((r) => r.bale_status === 'active' && r.token_status === 'active');
  const chosen = printable.filter((r) => selected.has(r.bale_serial)).map((r) => r.bale_serial);
  const target = chosen.length ? chosen : printable.map((r) => r.bale_serial);

  const columns: Column<BaleRow>[] = [
    { key: 'serial', header: 'Serial', mono: true, cell: (r) => r.bale_serial },
    { key: 'weight', header: 'Weight', numeric: true, cell: (r) => `${r.weight_kg} kg` },
    { key: 'code', header: 'Code', cell: codeBadge },
    { key: 'prints', header: 'Prints', numeric: true, cell: (r) => r.label_print_count },
    { key: 'scans', header: 'Scans', numeric: true, cell: (r) => r.scan_count },
    { key: 'last', header: 'Last printed', cell: (r) => (r.last_printed_at ? formatDateTime(r.last_printed_at) : '-') },
    {
      key: 'actions', header: 'Actions',
      cell: (r) => (
        <div className="flex items-center gap-1">
          <IconButton label={`Trace ${r.bale_serial}`} icon={<Search className="h-4 w-4" />} onClick={() => onTrace(r.bale_serial)} />
          {r.trace_url && r.token_status === 'active' && (
            <IconButton label={`Copy link for ${r.bale_serial}`} icon={<Copy className="h-4 w-4" />}
              onClick={() => void copyText(r.trace_url ?? '').then((ok) => (ok ? toast.success('Link copied') : toast.error('Copy failed')))} />
          )}
          {isAdmin && r.token_status === 'active' && (
            <IconButton label={`Revoke code for ${r.bale_serial}`} icon={<ShieldOff className="h-4 w-4" />}
              onClick={() => { setAction({ kind: 'revoke', row: r }); setReason(''); setError(null); }} />
          )}
          {isAdmin && r.bale_status === 'active' && (
            <IconButton label={`Regenerate code for ${r.bale_serial}`} icon={<RefreshCw className="h-4 w-4" />}
              onClick={() => { setAction({ kind: 'regenerate', row: r }); setReason(''); setError(null); }} />
          )}
        </div>
      ),
    },
  ];

  const submit = () => {
    if (!action) return;
    if (!reason.trim()) { setError('Give a reason.'); return; }
    const done = (msg: string) => { toast.success(msg); setAction(null); };
    const fail = (e: unknown) => setError(toApiError(e).message);
    if (action.kind === 'revoke' && action.row.token) {
      revoke.mutate({ token: action.row.token, reason: reason.trim() }, { onSuccess: () => done(`Code for ${action.row.bale_serial} revoked`), onError: fail });
    } else {
      regenerate.mutate({ serial: action.row.bale_serial, reason: reason.trim() }, { onSuccess: () => done(`New code for ${action.row.bale_serial}`), onError: fail });
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-sm text-muted">
          {chosen.length ? `${chosen.length} selected` : `${printable.length} bales with an active code`}
        </p>
        <Button size="sm" leftIcon={<Printer className="h-4 w-4" />} disabled={!target.length} onClick={() => setPrinting(true)}>
          Print labels ({target.length})
        </Button>
        <Button size="sm" variant="secondary" leftIcon={<Archive className="h-4 w-4" />} disabled={!target.length}
          onClick={() => void download(qrApi.zipPath, `${heapId}_qr.zip`, { serials: target })
            .catch((e: unknown) => toast.error('The download failed', toApiError(e).message))}>
          ZIP of PNGs
        </Button>
      </div>
      <DataTable caption={`Bales of ${heapId}`} columns={columns} rows={rows} rowKey={(r) => r.bale_serial} loading={loading}
        selectable selected={selected} onSelectedChange={setSelected}
        empty={<EmptyState compact title="No bales yet" description="Bales recorded in Heap get a code automatically." />} />
      <LabelPrintDialog open={printing} onClose={() => setPrinting(false)} serials={target} onPrinted={() => void refresh()} />
      <Dialog open={action !== null} onClose={() => setAction(null)} role="alertdialog" size="sm"
        title={action?.kind === 'revoke' ? `Revoke the code for ${action.row.bale_serial}?` : `New code for ${action?.row.bale_serial ?? ''}?`}
        description={action?.kind === 'revoke'
          ? 'Anyone scanning the old label will see "This code is not valid". This cannot be undone.'
          : 'The current code is revoked and a new one is made. Print and attach a new label.'}
        footer={<>
          <Button variant="secondary" onClick={() => setAction(null)}>Cancel</Button>
          <Button variant={action?.kind === 'revoke' ? 'danger' : 'primary'} loading={revoke.isPending || regenerate.isPending} onClick={submit}>
            {action?.kind === 'revoke' ? 'Revoke code' : 'Regenerate code'}
          </Button>
        </>}>
        <FormField label="Reason" required error={error}>
          <Textarea rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
        </FormField>
      </Dialog>
    </div>
  );
}
