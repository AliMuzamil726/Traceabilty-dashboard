import { useQuery } from '@tanstack/react-query';
import { Check, Minus } from 'lucide-react';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { DataTable, type Column } from '@/design-system/components/DataTable';
import { settingsApi, settingsKeys } from '../api/client';
import type { PermissionRow } from '../api/types';

function Mark({ held }: { held: boolean }) {
  return held ? (
    <span className="text-forest-700">
      <Check className="mx-auto h-4 w-4" aria-label="Yes" />
    </span>
  ) : (
    <span className="text-muted">
      <Minus className="mx-auto h-4 w-4" aria-label="No" />
    </span>
  );
}

/**
 * What each role may do, generated from the rules the backend enforces.
 *
 * It is read-only on purpose: the rules live in code, so this cannot drift from what
 * actually happens when somebody presses a button. Roles change when Login arrives.
 */
export default function PermissionsPage() {
  const permissions = useQuery({
    queryKey: settingsKeys.permissions,
    queryFn: ({ signal }) => settingsApi.permissions(signal),
  });

  const columns: Column<PermissionRow>[] = [
    {
      key: 'label',
      header: 'Action',
      cell: (row) => (
        <span className="flex flex-col">
          <span className="font-medium text-ink">{row.label}</span>
          <span className="text-sm text-muted">{row.description}</span>
        </span>
      ),
    },
    {
      key: 'module',
      header: 'Module',
      nowrap: true,
      cell: (row) => (row.module === null ? '-' : `Module ${row.module}`),
    },
    { key: 'officer', header: 'Officer', align: 'center', cell: (row) => <Mark held={row.officer} /> },
    { key: 'staff', header: 'Staff', align: 'center', cell: (row) => <Mark held={row.staff} /> },
    { key: 'admin', header: 'Administrator', align: 'center', cell: (row) => <Mark held={row.admin} /> },
  ];

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="Permissions"
        description="Who may do what. Generated from the rules the server enforces, so it cannot drift."
      />
      <Card padding="none">
        <DataTable
          columns={columns}
          rows={permissions.data ?? []}
          rowKey={(row) => row.key}
          caption="Capabilities by role"
          loading={permissions.isLoading}
        />
      </Card>
    </div>
  );
}
