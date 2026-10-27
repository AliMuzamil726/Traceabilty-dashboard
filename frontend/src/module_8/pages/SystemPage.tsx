import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { DataTable, type Column } from '@/design-system/components/DataTable';
import { KeyValueList } from '@/design-system/components/KeyValueList';
import { Skeleton } from '@/design-system/components/Skeleton';
import { settingsApi, settingsKeys } from '../api/client';
import type { HealthCheck } from '../api/types';
import { DummyDataCard } from '../components/DummyDataCard';

const ICON = {
  ok: <CheckCircle2 className="h-4 w-4 text-forest-700" aria-label="Working" />,
  warn: <AlertTriangle className="h-4 w-4 text-wheat-600" aria-label="Worth a look" />,
  fail: <XCircle className="h-4 w-4 text-danger" aria-label="Not working" />,
};

/** What this installation is: versions, sizes, counts and health. */
export default function SystemPage() {
  const system = useQuery({
    queryKey: settingsKeys.system,
    queryFn: ({ signal }) => settingsApi.system(signal),
  });
  const dummy = useQuery({
    queryKey: settingsKeys.dummy,
    queryFn: ({ signal }) => settingsApi.dummyData(signal),
  });

  const info = system.data;
  const countColumns: Column<{ table: string; rows: number }>[] = [
    { key: 'table', header: 'Table', mono: true, cell: (row) => row.table },
    {
      key: 'rows',
      header: 'Rows',
      numeric: true,
      cell: (row) => (row.rows < 0 ? 'Not readable' : row.rows.toLocaleString()),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <SectionHeader
        title="System information"
        description="What is running, how much is in it, and whether everything it depends on answers."
      />

      {system.isLoading || !info ? (
        <Skeleton className="h-64 w-full" shape="block" />
      ) : (
        <>
          <Card padding="md">
            <SectionHeader title="This installation" />
            <div className="mt-3">
              <KeyValueList
                columns={2}
                items={[
                  { label: 'Version', value: String(info.app.version ?? '-'), mono: true },
                  { label: 'Environment', value: String(info.app.environment ?? '-') },
                  { label: 'Python', value: String(info.runtime.python ?? '-'), mono: true },
                  { label: 'Node', value: String(info.runtime.node ?? 'Not on this machine'), mono: true },
                  { label: 'Database', value: String(info.database.dialect ?? '-'), mono: true },
                  {
                    label: 'Database size',
                    value: info.database.size_bytes
                      ? `${(Number(info.database.size_bytes) / (1024 * 1024)).toFixed(1)} MB`
                      : 'Not a file',
                    mono: true,
                  },
                  { label: 'Connection', value: String(info.database.url ?? '-'), mono: true },
                  { label: 'Time zone', value: String(info.app.time_zone ?? 'UTC') },
                ]}
              />
            </div>
          </Card>

          <Card padding="md">
            <SectionHeader
              title="Health"
              description="Checked when this page loads."
            />
            <ul className="mt-3 flex flex-col divide-y divide-line">
              {info.health.map((check: HealthCheck) => (
                <li key={check.key} className="flex items-start gap-3 py-2.5">
                  <span className="mt-0.5 shrink-0">{ICON[check.status]}</span>
                  <span className="min-w-0">
                    <span className="block text-base font-medium text-ink">{check.label}</span>
                    <span className="block text-sm text-muted">{check.detail}</span>
                  </span>
                </li>
              ))}
            </ul>
          </Card>

          <Card padding="none">
            <div className="p-4 pb-0">
              <SectionHeader title="Records" description="How much is in the database." />
            </div>
            <div className="mt-3">
              <DataTable
                columns={countColumns}
                rows={info.counts}
                rowKey={(row) => row.table}
                caption="Rows per table"
                maxHeight="24rem"
              />
            </div>
          </Card>
        </>
      )}

      <DummyDataCard data={dummy.data} />
    </div>
  );
}
