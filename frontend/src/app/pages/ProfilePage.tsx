import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Camera, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, apiRequest } from '@/core/api/client';
import { toApiError } from '@/core/api/errors';
import type { CurrentOfficer } from '@/core/api/types';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { roleLabel } from '@/core/utils/format';
import { isPhoneForCountry, phoneInput } from '@/core/utils/validators';
import { Button } from '@/design-system/components/Button';
import { Card, SectionHeader } from '@/design-system/components/Card';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { PageHeader } from '@/design-system/components/PageHeader';
import { Skeleton } from '@/design-system/components/Skeleton';
import { toast } from '@/design-system/components/toastStore';
import { Avatar } from '@/shared/components/Avatar';
import { PhotoCropDialog } from '@/shared/components/PhotoCropDialog';
import { PageContainer } from '../layout/PageContainer';

interface Details {
  full_name: string;
  email: string;
  phone: string;
}

const BLANK_PASSWORD = { current_password: '', new_password: '', repeat: '' };

/** What a number looks like where the officer works; the only hint worth giving. */
const MOBILE_EXAMPLE: Record<string, string> = { PK: '0300-1234567', GB: '07700 900123' };

/**
 * A person's own account: photo, contact details, password, and sign-out option.
 * Enabled profile photo upload (Add photo / Change photo / Remove) for all roles
 * including Field Officers.
 */
export default function ProfilePage() {
  const queryClient = useQueryClient();
  const me = useCurrentOfficer();
  const officer = me.data;
  const isAdmin = officer?.role === 'admin';
  const fileInput = useRef<HTMLInputElement>(null);

  const [details, setDetails] = useState<Details>({ full_name: '', email: '', phone: '' });
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [password, setPassword] = useState(BLANK_PASSWORD);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [cropSrc, setCropSrc] = useState<string | null>(null);
  const [cropOpen, setCropOpen] = useState(false);

  useEffect(() => {
    if (officer) {
      setDetails({ full_name: officer.full_name, email: officer.email ?? '', phone: officer.phone ?? '' });
    }
  }, [officer]);

  const refresh = (updated: CurrentOfficer) => {
    queryClient.setQueryData(['officers', 'me', updated.id], updated);
    void queryClient.invalidateQueries({ queryKey: ['officers'] });
  };

  const saveDetails = useMutation({
    mutationFn: () =>
      api.put<CurrentOfficer>('/v1/officers/me', {
        ...(isAdmin ? { full_name: details.full_name.trim() } : {}),
        email: details.email.trim() || null,
        phone: details.phone.trim(),
      }),
    onSuccess: (updated) => {
      refresh(updated);
      toast.success('Profile saved');
    },
    onError: (e) => toast.error('Not saved', toApiError(e).message),
  });

  const savePhoto = useMutation({
    mutationFn: (blob: Blob) => {
      const body = new FormData();
      body.append('file', blob, 'profile.jpg');
      return apiRequest<CurrentOfficer>('/v1/officers/me/photo', { method: 'POST', body });
    },
    onSuccess: (updated) => {
      refresh(updated);
      setCropOpen(false);
      if (cropSrc) { URL.revokeObjectURL(cropSrc); setCropSrc(null); }
      toast.success('Photo updated');
    },
    onError: (e) => toast.error('Photo not saved', toApiError(e).message),
  });

  const removePhoto = useMutation({
    mutationFn: () => api.delete<CurrentOfficer>('/v1/officers/me/photo'),
    onSuccess: (updated) => {
      refresh(updated);
      toast.success('Photo removed');
    },
    onError: (e) => toast.error('Photo not removed', toApiError(e).message),
  });

  const changePassword = useMutation({
    mutationFn: () =>
      api.post<CurrentOfficer>('/v1/officers/me/password', {
        current_password: password.current_password,
        new_password: password.new_password,
      }),
    onSuccess: () => {
      setPassword(BLANK_PASSWORD);
      setPasswordError(null);
      toast.success('Password changed', 'Use the new password next time you sign in.');
    },
    onError: (e) => setPasswordError(toApiError(e).message),
  });

  const onPassword = (e: FormEvent) => {
    e.preventDefault();
    if (password.new_password.length < 8) {
      setPasswordError('A password needs at least 8 characters.');
      return;
    }
    if (password.new_password !== password.repeat) {
      setPasswordError('The two new passwords do not match.');
      return;
    }
    setPasswordError(null);
    changePassword.mutate();
  };

  if (!officer) {
    return (
      <PageContainer>
        <Skeleton className="h-64 w-full" />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <PageHeader title="My profile" />

        <Card padding="lg">
          <div className="flex flex-wrap items-center gap-4">
            <Avatar officerId={officer.id} name={officer.full_name} hasPhoto={officer.has_photo} size="lg" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-lg font-semibold text-ink">{officer.full_name}</div>
              <div className="text-sm text-muted">
                {roleLabel(officer.role)} · {officer.code}
                {officer.field_office_name ? ` · ${officer.field_office_name}` : ''}
              </div>
              <p className="mt-1 text-xs text-muted">
                Upload a JPEG, PNG or WebP profile picture (up to 5 MB).
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInput}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    if (cropSrc) URL.revokeObjectURL(cropSrc);
                    setCropSrc(URL.createObjectURL(file));
                    setCropOpen(true);
                  }
                  e.target.value = '';
                }}
              />
              <Button
                variant="secondary"
                size="sm"
                loading={savePhoto.isPending}
                leftIcon={<Camera className="h-4 w-4" />}
                onClick={() => fileInput.current?.click()}
              >
                {officer.has_photo ? 'Change photo' : 'Add photo'}
              </Button>
              {officer.has_photo && (
                <Button
                  variant="ghost"
                  size="sm"
                  loading={removePhoto.isPending}
                  leftIcon={<Trash2 className="h-4 w-4" />}
                  onClick={() => removePhoto.mutate()}
                >
                  Remove
                </Button>
              )}
            </div>
          </div>
        </Card>

        <Card padding="lg">
          <SectionHeader title="My details" />
          <form
            className="mt-4 flex flex-col gap-4"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              const mobile = details.phone.trim();
              if (!mobile) {
                setDetailsError('A mobile number is required so an administrator can reach you.');
                return;
              }
              if (!isPhoneForCountry(mobile, officer.country)) {
                setDetailsError(
                  `Enter a valid mobile number, for example ${MOBILE_EXAMPLE[officer.country] ?? '0300-1234567'}.`,
                );
                return;
              }
              setDetailsError(null);
              saveDetails.mutate();
            }}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                label="Full name"
                className="sm:col-span-2"
                hint={isAdmin ? undefined : 'Only an administrator can change a name.'}
              >
                <Input
                  value={details.full_name}
                  onChange={(e) => setDetails({ ...details, full_name: e.target.value })}
                  disabled={!isAdmin}
                  maxLength={120}
                />
              </FormField>
              <FormField label="Email">
                <Input
                  type="email"
                  value={details.email}
                  onChange={(e) => setDetails({ ...details, email: e.target.value })}
                  maxLength={254}
                />
              </FormField>
              <FormField
                label="Mobile"
                required
                error={detailsError}
                hint={`Digits only, for example ${MOBILE_EXAMPLE[officer.country] ?? '0300-1234567'}.`}
              >
                <Input
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  value={details.phone}
                  onChange={(e) => {
                    setDetails({ ...details, phone: phoneInput(e.target.value) });
                    if (detailsError) setDetailsError(null);
                  }}
                  maxLength={16}
                />
              </FormField>
            </div>
            <div className="flex justify-end border-t border-line pt-4">
              <Button type="submit" loading={saveDetails.isPending}>
                Save details
              </Button>
            </div>
          </form>
        </Card>

        <Card padding="lg">
          <SectionHeader title="Password" />
          <form className="mt-4 flex flex-col gap-4" onSubmit={onPassword}>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Current password" className="sm:col-span-2">
                <Input
                  type="password"
                  autoComplete="current-password"
                  value={password.current_password}
                  onChange={(e) => setPassword({ ...password, current_password: e.target.value })}
                />
              </FormField>
              <FormField label="New password" hint="At least 8 characters.">
                <Input
                  type="password"
                  autoComplete="new-password"
                  value={password.new_password}
                  onChange={(e) => setPassword({ ...password, new_password: e.target.value })}
                />
              </FormField>
              <FormField label="Repeat new password" error={passwordError}>
                <Input
                  type="password"
                  autoComplete="new-password"
                  value={password.repeat}
                  onChange={(e) => setPassword({ ...password, repeat: e.target.value })}
                />
              </FormField>
            </div>
            <div className="flex justify-end border-t border-line pt-4">
              <Button
                type="submit"
                loading={changePassword.isPending}
                disabled={!password.current_password || !password.new_password}
              >
                Change password
              </Button>
            </div>
          </form>
        </Card>
      </div>

      <PhotoCropDialog
        imageSrc={cropSrc}
        open={cropOpen}
        onClose={() => {
          setCropOpen(false);
          if (cropSrc) { URL.revokeObjectURL(cropSrc); setCropSrc(null); }
        }}
        onCropped={(blob) => savePhoto.mutate(blob)}
        loading={savePhoto.isPending}
      />
    </PageContainer>
  );
}
