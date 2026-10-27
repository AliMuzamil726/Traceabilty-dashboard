import { ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatDecimal } from '@/core/utils/format';
import { Badge, Card, KeyValueList } from '@/design-system/components';
import type { Book } from '../api/types';

/** Who and where this fieldbook is for. Links back to the farmer in Register Farmer. */
export function FarmerSideCard({ book }: { book: Book }) {
  const { farmer, field } = book;
  const area = book.crop === 'cotton' ? `${formatDecimal(field.area_acre)} acres` : `${formatDecimal(field.area_ha)} ha`;
  return (
    <Card padding="md" aria-label="Farmer">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-xs text-muted">SAWIE {farmer.sawie_id}</p>
          <h3 className="truncate text-base font-semibold text-ink">{farmer.name}</h3>
        </div>
        <Badge tone="accent" size="sm">
          {book.crop === 'cotton' ? 'Cotton' : 'Hemp'}
        </Badge>
      </div>
      <KeyValueList
        className="mt-3"
        items={[
          { label: 'Field', value: field.field_id, mono: true },
          { label: 'Mapped area', value: area },
          { label: 'Season', value: String(book.season_year) },
          ...(farmer.home_office_licence_no ? [{ label: 'Licence', value: farmer.home_office_licence_no, mono: true }] : []),
        ]}
      />
      <Link
        to={`/register/farmers/${farmer.id}`}
        className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-forest-700 hover:text-forest-900"
      >
        Farmer profile
        <ExternalLink className="h-3.5 w-3.5" aria-hidden />
      </Link>
    </Card>
  );
}
