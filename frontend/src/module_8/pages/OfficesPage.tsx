import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useState } from 'react';
import { ApiError } from '@/core/api/errors';
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
import type { Office } from '../api/types';

/** Field offices: the teams farmers and officers belong to. */
export default function OfficesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Office | null>(null);
  const [creating, setCreating] = useState(false);

  const offices = useQuery({
    queryKey: settingsKeys.offices,
    queryFn: ({ signal }) => settingsApi.offices(signal),
  });

  const columns: Column<Office>[] = [
    { key: 'code', header: 'Code', mono: true, width: '110px', cell: (row) => row.code },
    { key: 'name', header: 'Name', cell: (row) => row.name },
    { key: 'country', header: 'Country', nowrap: true, cell: (row) => row.country },
    {
      key: 'area',
      header: 'Covers',
      cell: (row) => [row.province, row.district].filter(Boolean).join(', ') || '-',
    },
    { key: 'officers', header: 'Officers', numeric: true, cell: (row) => row.officer_count },
    { key: 'usage', header: 'Farmers', numeric: true, cell: (row) => row.usage },
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
      key: 'actions',
      header: 'Actions',
      align: 'right',
      cell: (row) => (
        <Button variant="ghost" size="sm" onClick={() => setEditing(row)}>
          Edit
        </Button>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="Field offices"
        description="Each farmer and officer belongs to one. Deactivating hides it from new forms only."
        actions={
          <Button size="sm" onClick={() => setCreating(true)} leftIcon={<Plus className="h-4 w-4" aria-hidden />}>
            Add field office
          </Button>
        }
      />
      <Card padding="none">
        <DataTable
          columns={columns}
          rows={offices.data ?? []}
          rowKey={(row) => row.id}
          caption="Field offices"
          loading={offices.isLoading}
        />
      </Card>

      <OfficeDialog
        open={creating || editing !== null}
        office={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
        onSaved={() => void queryClient.invalidateQueries({ queryKey: settingsKeys.all })}
      />
    </div>
  );
}

function OfficeDialog({
  open,
  office,
  onClose,
  onSaved,
}: {
  open: boolean;
  office: Office | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const blank = { code: '', name: '', country: 'PK', province: '', district: '', active: true };
  const [form, setForm] = useState(blank);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const key = office?.id ?? (open ? 'new' : null);
  if (open && key !== loadedFor) {
    setLoadedFor(key);
    setForm(
      office
        ? {
            code: office.code,
            name: office.name,
            country: office.country,
            province: office.province ?? '',
            district: office.district ?? '',
            active: office.active,
          }
        : blank,
    );
    setError(null);
  }

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = {
        ...form,
        province: form.province || null,
        district: form.district || null,
      };
      if (office) await settingsApi.updateOffice(office.id, body as never);
      else await settingsApi.createOffice(body as never);
      toast.success('Field office saved', form.name);
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
      title={office ? `Edit ${office.name}` : 'Add a field office'}
      dismissible={!busy}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} loading={busy}>
            Save field office
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        {error && (
          <p className="rounded-control bg-danger-tint px-3 py-2 text-sm text-danger">{error}</p>
        )}
        <FormField label="Code" required hint="Short and stable, for example PK-MUL.">
          <Input
            value={form.code}
            mono
            disabled={office !== null}
            onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
          />
        </FormField>
        <FormField label="Name" required>
          <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
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
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Province or region">
            <Input
              value={form.province}
              onChange={(event) => setForm({ ...form, province: event.target.value })}
            />
          </FormField>
          <FormField label="District or county">
            <Input
              value={form.district}
              onChange={(event) => setForm({ ...form, district: event.target.value })}
            />
          </FormField>
        </div>
        {office && (
          <Switch
            checked={form.active}
            onChange={(active) => setForm({ ...form, active })}
            label="Active"
            description="Deactivating keeps every farmer and officer that names this office."
          />
        )}
      </div>
    </Dialog>
  );
}
