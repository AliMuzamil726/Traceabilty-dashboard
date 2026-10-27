import { useState } from 'react';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { KeyValueList } from '@/design-system/components/KeyValueList';
import { toast } from '@/design-system/components/toastStore';
import { settingsApi } from '../api/client';
import { useAppConfig } from '../hooks/useAppConfig';
import { GroupPage } from './GroupPage';

/** The address a scanned label opens, and how a sheet of labels is laid out. */
export default function QrLabelsPage() {
  const config = useAppConfig();
  const [testing, setTesting] = useState(false);
  const baseUrl = config.data?.qr.public_base_url ?? '';
  const local = /localhost|127\.0\.0\.1|0\.0\.0\.0/.test(baseUrl);
  const grid = (config.data?.settings['qr.label_grid'] ?? {}) as Record<string, number>;

  const test = async () => {
    setTesting(true);
    try {
      const result = await settingsApi.testUrl(baseUrl);
      if (result.warning) toast.warning('The address answered, but', result.warning);
      else if (result.ok) toast.success('Address reached', result.detail);
      else toast.error('Address could not be reached', result.detail);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {local && (
        <p className="rounded-control border border-danger bg-danger-tint px-3 py-2 text-base text-ink">
          <strong className="font-medium text-danger">This address only works on this computer.</strong>{' '}
          A label printed now cannot be scanned by a farmer or a buyer. Set the public base URL to
          the address the server is reachable at before printing anything.
        </p>
      )}

      <GroupPage
        group="qr"
        title="QR and labels"
        description="Where a scanned code leads, and how labels are arranged on a sheet."
      >
        <div className="flex">
          <Button variant="secondary" size="sm" loading={testing} onClick={() => void test()}>
            Test the public address
          </Button>
        </div>
      </GroupPage>

      <Card padding="md">
        <SectionHeader
          title="Label sheet"
          description="One page, as the current grid describes it."
        />
        <div className="mt-3 grid gap-4 md:grid-cols-[minmax(0,16rem)_1fr]">
          <div
            className="aspect-[210/297] rounded-sm border border-line bg-surface p-1"
            role="img"
            aria-label={`A sheet of ${(grid.columns ?? 0) * (grid.rows ?? 0)} labels`}
          >
            <div
              className="grid h-full w-full gap-0.5"
              style={{
                gridTemplateColumns: `repeat(${Math.max(1, grid.columns ?? 3)}, minmax(0, 1fr))`,
                gridTemplateRows: `repeat(${Math.max(1, grid.rows ?? 8)}, minmax(0, 1fr))`,
              }}
            >
              {Array.from({ length: Math.max(1, (grid.columns ?? 3) * (grid.rows ?? 8)) }, (_, index) => (
                <span key={index} className="rounded-[2px] border border-dashed border-line bg-canvas" />
              ))}
            </div>
          </div>
          <KeyValueList
            items={[
              { label: 'Columns', value: String(grid.columns ?? '-'), mono: true },
              { label: 'Rows', value: String(grid.rows ?? '-'), mono: true },
              { label: 'Labels per page', value: String((grid.columns ?? 0) * (grid.rows ?? 0)), mono: true },
              { label: 'Caption', value: config.data?.qr.label_caption || 'None' },
            ]}
          />
        </div>
      </Card>

      <Card padding="md">
        <SectionHeader
          title="What the public page never shows"
          description="Fixed in code. There is no switch for these, by design."
        />
        <ul className="mt-3 flex list-disc flex-col gap-1 pl-5 text-base text-ink">
          <li>The farmer's name, father's name or farm name</li>
          <li>Identity and licence numbers</li>
          <li>Phone numbers and addresses</li>
          <li>Field boundaries, pins and coordinates</li>
          <li>Officer names and internal identifiers</li>
        </ul>
        <p className="mt-2 text-sm text-muted">
          A buyer scanning a bale sees the district, the crop, the season and the chain of custody,
          and nothing that identifies a person.
        </p>
      </Card>
    </div>
  );
}
