import { useMutation, useQueryClient } from '@tanstack/react-query';
import { LogIn } from 'lucide-react';
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { api } from '@/core/api/client';
import { toApiError } from '@/core/api/errors';
import type { Role, SignInResponse } from '@/core/api/types';
import { useOfficerDirectory } from '@/core/hooks/useSharedData';
import { useOfficerStore } from '@/core/store/officerStore';
import { Button } from '@/design-system/components/Button';
import { FormField } from '@/design-system/components/FormField';
import { Input } from '@/design-system/components/Input';
import { SegmentedControl } from '@/design-system/components/SegmentedControl';
import { Select } from '@/design-system/components/Select';
import { BrandLogo } from '../layout/BrandMark';

const ROLES: { value: Role; label: string }[] = [
  { value: 'admin', label: 'Admin' },
  { value: 'staff', label: 'Staff' },
  { value: 'officer', label: 'Field officer' },
];
const PICK_LABEL: Record<Role, string> = {
  admin: 'Administrator',
  staff: 'Staff member',
  officer: 'Field officer',
};

/**
 * Sign in: choose the account, type the password. The password is checked by the
 * server; every request afterwards still names the officer in a header, so this is a
 * sign-in screen rather than a security boundary (docs/KNOWN_LIMITATIONS.md).
 */
export default function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const signedIn = useOfficerStore((s) => s.signedIn && Boolean(s.officerId) && Boolean(s.token));
  const signIn = useOfficerStore((s) => s.signIn);
  const { data, isLoading, isError } = useOfficerDirectory();
  const [role, setRole] = useState<Role>('admin');
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const people = useMemo(() => (data ?? []).filter((o) => o.role === role && o.active), [data, role]);

  useEffect(() => {
    setUserId(people[0]?.id ?? '');
  }, [people]);

  const submit = useMutation({
    mutationFn: () =>
      api.post<SignInResponse>('/v1/officers/sign-in', { officer_id: userId, password }),
    onSuccess: (result) => {
      queryClient.clear();
      signIn(result.officer.id, result.token);
      navigate('/', { replace: true });
    },
    onError: (e) => setError(toApiError(e).message),
  });

  if (signedIn) return <Navigate to="/" replace />;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (userId && password) submit.mutate();
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-10">
      {/* Full-bleed background */}
      <img
        src="/login-bg.jpg"
        alt=""
        aria-hidden
        className="pointer-events-none absolute inset-0 h-full w-full object-cover"
      />
      {/* Dark overlay for contrast */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-forest-950/70 via-forest-950/50 to-forest-950/80" />

      <form
        onSubmit={onSubmit}
        className="relative z-10 w-full max-w-sm rounded-card border border-white/10 bg-white/95 p-6 shadow-[0_8px_40px_rgba(21,34,27,0.3)] backdrop-blur-sm sm:p-8"
      >
        <BrandLogo className="mx-auto mb-6 h-auto w-full max-w-[280px]" />

        <div className="flex flex-col gap-4">
          <SegmentedControl
            aria-label="Sign in as"
            value={role}
            onChange={(next) => {
              setRole(next);
              setError(null);
            }}
            options={ROLES}
          />
          <FormField label={PICK_LABEL[role]}>
            <Select
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              disabled={isLoading || isError || people.length === 0}
              placeholder={isLoading ? 'Loading' : isError ? 'Server not reachable' : people.length ? undefined : 'No accounts'}
              options={people.map((o) => ({
                value: o.id,
                label: o.field_office ? `${o.full_name}, ${o.field_office.name}` : o.full_name,
              }))}
            />
          </FormField>
          <FormField label="Password" error={error}>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </FormField>
          <Button
            type="submit"
            disabled={!userId || !password}
            loading={submit.isPending}
            leftIcon={<LogIn className="h-4 w-4" />}
            className="mt-2 w-full"
          >
            Sign in
          </Button>
        </div>

        <p className="mt-5 text-center text-xs text-muted">
          Trace · Verify · Sustain
        </p>
      </form>
    </div>
  );
}
