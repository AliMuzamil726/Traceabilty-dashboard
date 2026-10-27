import { Info, MapPinPlus, TriangleAlert, UserCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatDate } from '@/core/utils/format';
import { buttonClasses } from '@/design-system/components/buttonStyles';
import { Card } from '@/design-system/components/Card';
import type { FarmerLookup } from '../api/types';
import { CROP_LABEL } from '../format';

export interface ExistingFarmerBannerProps {
  lookup: FarmerLookup;
}

/**
 * What the officer is told when the ID number is already registered.
 * Includes a direct "Add field to this farmer" button so an officer who looks up an
 * existing CNIC/ID can jump straight to mapping their new field.
 */
export function ExistingFarmerBanner({ lookup }: ExistingFarmerBannerProps) {
  if (!lookup.exists) return null;

  const registrar = lookup.registered_by?.full_name ?? 'another officer';
  const office = lookup.field_office?.name;
  const when = lookup.registered_at ? formatDate(lookup.registered_at) : null;

  if (lookup.crop_mismatch) {
    return (
      <Card
        padding="md"
        className="border-danger bg-danger-tint"
        role="alert"
        aria-live="polite"
      >
        <div className="flex items-start gap-3">
          <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden />
          <div className="min-w-0">
            <p className="font-medium text-ink">
              This farmer is already in the{' '}
              {lookup.registered_crop ? CROP_LABEL[lookup.registered_crop] : 'other'} programme
            </p>
            <p className="mt-1 text-base text-muted">
              SAWIE ID <span className="mono-id text-ink">{lookup.sawie_id}</span> is registered
              {office ? ` at ${office}` : ''}
              {when ? ` on ${when}` : ''}. One farmer belongs to one programme, so they cannot be
              registered again here. Switch the crop programme to continue with this farmer.
            </p>
            {lookup.farmer_id && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Link
                  to={`/register/farmers/${lookup.farmer_id}/fields/new`}
                  className={buttonClasses('primary', 'sm')}
                >
                  <MapPinPlus className="h-3.5 w-3.5" aria-hidden />
                  <span>Add field</span>
                </Link>
                <Link
                  to={`/register/farmers/${lookup.farmer_id}`}
                  className={buttonClasses('secondary', 'sm')}
                >
                  Open their record
                </Link>
              </div>
            )}
          </div>
        </div>
      </Card>
    );
  }

  const otherOfficer = lookup.registered_by_other_officer;
  return (
    <Card
      padding="md"
      className={otherOfficer ? 'border-wheat-300/70 bg-wheat-50' : 'border-forest-100 bg-forest-50'}
      aria-live="polite"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {otherOfficer ? (
            <Info className="mt-0.5 h-5 w-5 shrink-0 text-wheat-600" aria-hidden />
          ) : (
            <UserCheck className="mt-0.5 h-5 w-5 shrink-0 text-forest-700" aria-hidden />
          )}
          <div className="min-w-0">
            <p className="font-medium text-ink">
              Existing farmer found, SAWIE ID{' '}
              <span className="mono-id">{lookup.sawie_id}</span>
              {when ? `, registered by ${registrar} on ${when}` : `, registered by ${registrar}`}
            </p>
            <p className="mt-1 text-base text-muted">
              {otherOfficer
                ? `This record belongs to ${registrar}${office ? ` at ${office}` : ''}. You can still correct their details, and the change is recorded in the audit log. `
                : 'Their personal details are filled in below and can be corrected. '}
              This season&apos;s variety, tenure and previous crop are not pre-filled: enter them for
              this season, or jump straight to mapping a new field.
            </p>
            {lookup.field_count > 0 && (
              <p className="mt-1 text-sm text-muted">
                {lookup.field_count} field{lookup.field_count === 1 ? '' : 's'} already mapped.
              </p>
            )}
          </div>
        </div>

        {lookup.farmer_id && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Link
              to={`/register/farmers/${lookup.farmer_id}/fields/new`}
              className={buttonClasses('primary', 'sm')}
            >
              <MapPinPlus className="h-4 w-4" aria-hidden />
              <span>Add field for this farmer</span>
            </Link>
            <Link
              to={`/register/farmers/${lookup.farmer_id}`}
              className={buttonClasses('secondary', 'sm')}
            >
              View farmer
            </Link>
          </div>
        )}
      </div>
    </Card>
  );
}
