import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useState } from 'react';
import { ApiError } from '@/core/api/errors';
import { Badge } from '@/design-system/components/Badge';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { ConfirmDialog } from '@/design-system/components/ConfirmDialog';
import { DataTable, type Column } from '@/design-system/components/DataTable';
import { Dialog } from '@/design-system/components/Dialog';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { Select } from '@/design-system/components/Select';
import { Switch } from '@/design-system/components/Switch';
import { toast } from '@/design-system/components/toastStore';
import { settingsApi, settingsKeys } from '../api/client';
import type { Site } from '../api/types';

/** Ginners and processors: where deliveries arrive and heaps are built. */
export default function SitesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Site | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Site | null>(null);

  const sites = useQuery({
    queryKey: settingsKeys.sites({}),
    queryFn: ({ signal }) => settingsApi.sites({}, signal),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: settingsKeys.all });

  const columns: Column<Site>[] = [
    { key: 'code', header: 'Code', mono: true, width: '110px', cell: (row) => row.code },
    {
      key: 'name',
      header: 'Name',
      cell: (row) => (
        <span className="flex flex-col">
          <span className="font-medium text-ink">{row.name}</span>
          {row.address && <span className="text-sm text-muted">{row.address}</span>}
        </span>
      ),
    },
    { key: 'type', header: 'Type', nowrap: true, cell: (row) => (row.type === 'ginner' ? 'Ginner' : 'Processor') },
    { key: 'crop', header: 'Crop', nowrap: true, cell: (row) => (row.crop === 'cotton' ? 'Cotton' : 'Hemp') },
    {
      key: 'contact',
      header: 'Contact',
      cell: (row) =>
        row.contact_person ? `${row.contact_person}${row.contact_phone ? ` (${row.contact_phone})` : ''}` : '-',
    },
    {
      key: 'usage',
      header: 'Used by',
      numeric: true,
      cell: (row) =>
        row.usage === 0 ? (
          <span className="text-muted">Nothing yet</span>
        ) : (
          <span title={row.usage_breakdown.map((item) => `${item.label}: ${item.count}`).join(', ')}>
            {row.usage}
          </span>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      nowrap: true,
      cell: (row) => (row.active ? <Badge tone="success">Active</Badge> : <Badge tone="warning">Inactive</Badge>),
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
          {row.usage === 0 && (
            <Button variant="ghost" size="sm" onClick={() => setDeleting(row)}>
              Delete
            </Button>
          )}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="Ginners and processors"
        description="Every delivery arrives at one of these, and every heap is built at one."
        actions={
          <Button size="sm" onClick={() => setCreating(true)} leftIcon={<Plus className="h-4 w-4" aria-hidden />}>
            Add site
          </Button>
        }
      />
      <p className="rounded-control bg-forest-50 px-3 py-2 text-sm text-ink">
        A site code is printed into every heap ID made there, so once a site has deliveries or
        heaps its code is fixed. The name, address and contact can always be corrected.
      </p>

      <Card padding="none">
        <DataTable
          columns={columns}
          rows={sites.data ?? []}
          rowKey={(row) => row.id}
          caption="Ginners and processors"
          loading={sites.isLoading}
        />
      </Card>

      <SiteDialog
        open={creating || editing !== null}
        site={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
        onSaved={refresh}
      />

      <ConfirmDialog
        open={deleting !== null}
        title={`Delete ${deleting?.name ?? ''}?`}
        description="No delivery or heap uses this site, so it can be removed. If it may be used later, deactivate it instead."
        confirmLabel="Delete the site"
        destructive
        onCancel={() => setDeleting(null)}
        onConfirm={() => {
          const site = deleting;
          setDeleting(null);
          if (!site) return;
          void settingsApi
            .deleteSite(site.id)
            .then(() => {
              toast.success('Site deleted', site.name);
              refresh();
            })
            .catch((error: unknown) =>
              toast.error(
                'Could not delete the site',
                error instanceof ApiError ? error.message : 'Please try again.',
              ),
            );
        }}
      />
    </div>
  );
}

function SiteDialog({
  open,
  site,
  onClose,
  onSaved,
}: {
  open: boolean;
  site: Site | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const blank = {
    code: '',
    name: '',
    type: 'ginner',
    crop: 'cotton',
    country: 'PK',
    address: '',
    region: '',
    contact_person: '',
    contact_phone: '',
    active: true,
  };
  const [form, setForm] = useState(blank);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const key = site?.id ?? (open ? 'new' : null);
  if (open && key !== loadedFor) {
    setLoadedFor(key);
    setForm(
      site
        ? {
            code: site.code,
            name: site.name,
            type: site.type,
            crop: site.crop,
            country: site.country,
            address: site.address ?? '',
            region: site.region ?? '',
            contact_person: site.contact_person ?? '',
            contact_phone: site.contact_phone ?? '',
            active: site.active,
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
        address: form.address || null,
        region: form.region || null,
        contact_person: form.contact_person || null,
        contact_phone: form.contact_phone || null,
      };
      if (site) await settingsApi.updateSite(site.id, body as never);
      else await settingsApi.createSite(body as never);
      toast.success('Site saved', form.name);
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
      title={site ? `Edit ${site.name}` : 'Add a site'}
      size="lg"
      dismissible={!busy}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} loading={busy}>
            Save site
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        {error && (
          <p className="rounded-control bg-danger-tint px-3 py-2 text-sm text-danger">{error}</p>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            label="Code"
            required
            hint={site?.code_locked ? 'Fixed: heap IDs already carry it.' : 'Printed into every heap ID.'}
          >
            <Input
              value={form.code}
              mono
              disabled={site?.code_locked}
              onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
            />
          </FormField>
          <FormField label="Name" required>
            <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </FormField>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Type">
            <Select
              value={form.type}
              disabled={site !== null}
              onChange={(event) => setForm({ ...form, type: event.target.value })}
              options={[
                { value: 'ginner', label: 'Ginner' },
                { value: 'processor', label: 'Processor' },
              ]}
            />
          </FormField>
          <FormField label="Crop">
            <Select
              value={form.crop}
              disabled={site !== null}
              onChange={(event) => setForm({ ...form, crop: event.target.value })}
              options={[
                { value: 'cotton', label: 'Cotton' },
                { value: 'hemp', label: 'Hemp' },
              ]}
            />
          </FormField>
          <FormField label="Country">
            <Select
              value={form.country}
              disabled={site !== null}
              onChange={(event) => setForm({ ...form, country: event.target.value })}
              options={[
                { value: 'PK', label: 'Pakistan' },
                { value: 'GB', label: 'United Kingdom' },
              ]}
            />
          </FormField>
        </div>
        <FormField label="Address">
          <Input value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Region">
            <Input value={form.region} onChange={(event) => setForm({ ...form, region: event.target.value })} />
          </FormField>
          <FormField label="Contact person">
            <Input
              value={form.contact_person}
              onChange={(event) => setForm({ ...form, contact_person: event.target.value })}
            />
          </FormField>
          <FormField label="Contact phone">
            <Input
              value={form.contact_phone}
              onChange={(event) => setForm({ ...form, contact_phone: event.target.value })}
            />
          </FormField>
        </div>
        {site && (
          <Switch
            checked={form.active}
            onChange={(active) => setForm({ ...form, active })}
            label="Active"
            description="An inactive site keeps every delivery and heap it already holds."
          />
        )}
      </div>
    </Dialog>
  );
}
