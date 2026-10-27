import { ShieldAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { Card } from '@/design-system/components/Card';
import { EmptyState } from '@/design-system/components/EmptyState';
import { PageSkeleton } from '@/shared/components/PageSkeleton';

export interface AdminOnlyGateProps {
  children: ReactNode;
}

/**
 * Most of Settings is for administrators.
 *
 * The backend refuses anything else with 403, so this gate is about the explanation
 * rather than the protection: an officer who opens Settings should be told what they
 * are looking at and how to act as an administrator, not shown a bare error.
 */
export function AdminOnlyGate({ children }: AdminOnlyGateProps) {
  const me = useCurrentOfficer();

  if (me.isLoading) return <PageSkeleton />;
  if (me.data?.is_admin) return <>{children}</>;

  return (
    <Card padding="lg">
      <EmptyState
        icon={<ShieldAlert />}
        title="Administrator access required"
        description={
          'This part of Settings changes things every officer depends on, so only an ' +
          'administrator can open it. Use the officer switcher at the top of the screen to ' +
          'act as an administrator, or ask one to make the change. Your own preferences are ' +
          'on the My preferences screen and need no special access.'
        }
      />
    </Card>
  );
}
