import { Compass } from 'lucide-react';
import { Link } from 'react-router-dom';
import { buttonClasses } from '@/design-system/components/buttonStyles';
import { EmptyState } from '@/design-system/components/EmptyState';
import { PageContainer } from '@/app/layout/PageContainer';

export function NotFound() {
  return (
    <PageContainer>
      <EmptyState
        icon={<Compass />}
        title="Page not found"
        description="This address does not match any page in SAWIE. Use the sidebar, or go back to the dashboard."
        action={
          <Link to="/" className={buttonClasses('primary')}>
            Go to dashboard
          </Link>
        }
      />
    </PageContainer>
  );
}
