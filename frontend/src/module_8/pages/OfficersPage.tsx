import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Plus, Upload } from 'lucide-react';
import { useState } from 'react';
import { ApiError } from '@/core/api/errors';
import { formatDate } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { DataTable, type Column } from '@/design-system/components/DataTable';
import { Dialog } from '@/design-system/components/Dialog';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { Select } from '@/design-system/components/Select';
import { Switch } from '@/design-system/components/Switch';
import { toast } from '@/design-system/components/toastStore';
import { settingsApi, settingsKeys } from '../api/client';
import type { Officer } from '../api/types';
import { CsvImportDialog } from '../components/CsvImportDialog';

interface OfficerForm {
  code: string;
  full_name: string;
  email: string;
  phone: string;
  role: 'officer' | 'staff' | 'admin';
  country: string;
  field_office_id: string;
  active: boolean;
}

const BLANK: OfficerForm = {
  code: '',
  full_name: '',
  email: '',
  phone: '',
  role: 'officer',
  country: 'PK',
  field_office_id: '',
  active: true,
};

/** Officers: who may use the product, and which field office they belong to. */
export default function OfficersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Officer | null>(null);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);

  const officers = useQuery({
    queryKey: settingsKeys.officers({ q: search }),
    queryFn: ({ signal }) => settingsApi.officers({ q: search || undefined }, signal),
  });
  const offices = useQuery({
    queryKey: settingsKeys.offices,
    queryFn: ({ signal }) => settingsApi.offices(signal),
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: settingsKeys.all });

  const setActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      settingsApi.setOfficerActive(id, active),
    onSuccess: (row) => {
      toast.success(row.active ? 'Officer activated' : 'Officer deactivated', row.full_name);
      refresh();
    },
    onError: (error: unknown) =>
      toast.error(
        'Could not change the officer',
        error instanceof ApiError ? error.message : 'Please try again.',
      ),
  });

  const columns: Column<Officer>[] = [
    { key: 'code', header: 'Code', mono: true, width: '120px', cell: (row) => row.code },
    {
      key: 'full_name',
      header: 'Name',
      cell: (row) => (
        <span className="flex flex-col">
          <span className="font-medium text-ink">{row.full_name}</span>
          {row.email && <span className="text-sm text-muted">{row.email}</span>}
        </span>
      ),
    },
    { key: 'phone', header: 'Phone', mono: true, cell: (row) => row.phone ?? '-' },
    { key: 'office', header: 'Field office', cell: (row) => row.field_office_name ?? '-' },
    {
      key: 'role',
      header: 'Role',
      cell: (row) =>
        row.role === 'admin' ? (
          <Badge tone="accent">Administrator</Badge>
        ) : row.role === 'staff' ? (
          <Badge tone="neutral">Staff</Badge>
        ) : (
          <Badge tone="neutral">Officer</Badge>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      nowrap: true,
      cell: (row) => (
        <span className="flex items-center gap-2">
          {row.active ? <Badge tone="success">Active</Badge> : <Badge tone="warning">Inactive</Badge>}
          {row.is_dummy && <Badge tone="neutral">Dummy</Badge>}
        </span>
      ),
    },
    {
      key: 'last_activity',
      header: 'Last activity',
      nowrap: true,
      cell: (row) => (row.last_activity ? formatDate(row.last_activity) : 'Never'),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      nowrap: true,
      cell: (row) => (
        <span className="flex items-center justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={() => setEditing(row)}>
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={row.active && !row.can_deactivate}
            onClick={() => setActive.mutate({ id: row.id, active: !row.active })}
          >
            {row.active ? 'Deactivate' : 'Activate'}
          </Button>
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="Officers"
        description="Everyone who registers farmers, fills in fieldbooks or records deliveries."
        actions={
          <div className="flex flex-wrap items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setImporting(true)}
              leftIcon={<Upload className="h-4 w-4" aria-hidden />}
            >
              Import
            </Button>
            <a
              href={settingsApi.officersCsvUrl()}
              className="inline-flex items-center gap-1.5 rounded-control px-2.5 py-1.5 text-sm text-ink hover:bg-canvas"
            >
              <Download className="h-4 w-4" aria-hidden />
              Export
            </a>
            <Button size="sm" onClick={() => setCreating(true)} leftIcon={<Plus className="h-4 w-4" aria-hidden />}>
              Add officer
            </Button>
          </div>
        }
      />

      <p className="rounded-control bg-forest-50 px-3 py-2 text-sm text-ink">
        A new officer starts on the shared default password and changes it from My profile
        after signing in. This screen manages who exists, their field office and their role;
        it never edits a password.
      </p>

      <div className="max-w-sm">
        <FormField label="Search" hideLabel>
          <Input
            value={search}
            placeholder="Search by name or code"
            onChange={(event) => setSearch(event.target.value)}
          />
        </FormField>
      </div>

      <Card padding="none">
        <DataTable
          columns={columns}
          rows={officers.data ?? []}
          rowKey={(row) => row.id}
          caption="Officers"
          loading={officers.isLoading}
          empty={<p className="px-4 py-10 text-center text-muted">No officer matches that search.</p>}
        />
      </Card>

      <OfficerDialog
        open={creating || editing !== null}
        officer={editing}
        offices={(offices.data ?? []).map((office) => ({
          value: office.id,
          label: `${office.code} - ${office.name}`,
        }))}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
        onSaved={refresh}
      />

      <CsvImportDialog
        open={importing}
        onClose={() => setImporting(false)}
        title="Import officers"
        columns={['code', 'full_name', 'role', 'country', 'office_code', 'email', 'phone']}
        onImport={(text, dryRun) => settingsApi.importOfficers(text, dryRun)}
        onDone={refresh}
      />
    </div>
  );
}

interface OfficerDialogProps {
  open: boolean;
  officer: Officer | null;
  offices: { value: string; label: string }[];
  onClose: () => void;
  onSaved: () => void;
}

function OfficerDialog({ open, officer, offices, onClose, onSaved }: OfficerDialogProps) {
  const [form, setForm] = useState<OfficerForm>(() => ({ ...BLANK }));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  // Fill the form the first time the dialog opens for a given officer.
  const key = officer?.id ?? (open ? 'new' : null);
  if (open && key !== loadedFor) {
    setLoadedFor(key);
    setForm(
      officer
        ? {
            code: officer.code,
            full_name: officer.full_name,
            email: officer.email ?? '',
            phone: officer.phone ?? '',
            role: officer.role,
            country: officer.country,
            field_office_id: officer.field_office_id ?? '',
            active: officer.active,
          }
        : { ...BLANK },
    );
    setError(null);
  }

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = {
        ...form,
        email: form.email || null,
        phone: form.phone || null,
        field_office_id: form.field_office_id || null,
      };
      if (officer) {
        await settingsApi.updateOfficer(officer.id, body as never);
        toast.success('Officer saved', form.full_name);
      } else {
        await settingsApi.createOfficer(body as never);
        toast.success('Officer added', form.full_name);
      }
      onSaved();
      setLoadedFor(null);
      onClose();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not be saved.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={() => {
        setLoadedFor(null);
        onClose();
      }}
      title={officer ? `Edit ${officer.full_name}` : 'Add an officer'}
      dismissible={!busy}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} loading={busy}>
            {officer ? 'Save officer' : 'Add officer'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        {error && (
          <p className="rounded-control bg-danger-tint px-3 py-2 text-sm text-danger">{error}</p>
        )}
        <FormField label="Code" hint="How the officer is identified, for example PK-MUL-02." required>
          <Input
            value={form.code}
            mono
            disabled={officer !== null}
            onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
          />
        </FormField>
        <FormField label="Full name" required>
          <Input
            value={form.full_name}
            onChange={(event) => setForm({ ...form, full_name: event.target.value })}
          />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Phone">
            <Input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
          </FormField>
          <FormField label="Email">
            <Input
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </FormField>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Role">
            <Select
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value as OfficerForm['role'] })}
              options={[
                { value: 'officer', label: 'Officer' },
                { value: 'staff', label: 'Staff' },
                { value: 'admin', label: 'Administrator' },
              ]}
            />
          </FormField>
          <FormField label="Country">
            <Select
              value={form.country}
              onChange={(event) => setForm({ ...form, country: event.target.value })}
              options={[
                { value: 'PK', label: 'Pakistan' },
                { value: 'GB', label: 'United Kingdom' },
              ]}
            />
          </FormField>
        </div>
        <FormField label="Field office">
          <Select
            value={form.field_office_id}
            onChange={(event) => setForm({ ...form, field_office_id: event.target.value })}
            options={offices}
            placeholder="No field office"
          />
        </FormField>
        {officer && (
          <Switch
            checked={form.active}
            onChange={(active) => setForm({ ...form, active })}
            label="Active"
            description="An inactive officer keeps every record they made and cannot act."
          />
        )}
      </div>
    </Dialog>
  );
}
