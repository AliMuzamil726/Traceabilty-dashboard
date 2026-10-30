import { useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useCurrentOfficer } from '@/core/hooks/useSharedData';
import { useOfficerStore } from '@/core/store/officerStore';
import { canOpen, showsTopbarTools } from '@/core/utils/access';
import { PageSkeleton } from '@/shared/components/PageSkeleton';
import { useIsDesktop } from '@/core/hooks/useMediaQuery';
import { useUiStore } from '@/core/store/uiStore';
import { Drawer } from '@/design-system/components/Dialog';
import { Toaster } from '@/design-system/components/Toast';
import { ErrorBoundary } from '@/shared/components/ErrorBoundary';
import { OfficerShell } from './OfficerShell';
import { Sidebar, SidebarContent } from './Sidebar';
import { GlobalSearch } from './GlobalSearch';
import { Topbar } from './Topbar';

export function AppShell() {
  const { pathname } = useLocation();
  const isDesktop = useIsDesktop();
  const mobileNavOpen = useUiStore((s) => s.mobileNavOpen);
  const setMobileNavOpen = useUiStore((s) => s.setMobileNavOpen);

  const signedIn = useOfficerStore((s) => s.signedIn && Boolean(s.officerId) && Boolean(s.token));
  const me = useCurrentOfficer();
  const role = me.data?.role;

  useEffect(() => {
    if (isDesktop) setMobileNavOpen(false);
  }, [isDesktop, setMobileNavOpen]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname, setMobileNavOpen]);

  if (!signedIn) return <Navigate to="/login" replace />;
  if (me.isError) return <Navigate to="/login" replace />;
  if (role && !canOpen(role, pathname)) return <Navigate to="/" replace />;

  // A field officer works on a phone and has two modules: their frame is its own.
  if (role === 'officer') {
    return (
      <>
        <OfficerShell>
          <ErrorBoundary key={pathname}>
            <Outlet />
          </ErrorBoundary>
        </OfficerShell>
        <Toaster />
      </>
    );
  }

  return (
    <div className="flex min-h-screen bg-canvas">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-control focus:bg-surface focus:px-4 focus:py-2 focus:shadow-2">
        Skip to content
      </a>
      <Sidebar />
      <Drawer
        open={!isDesktop && mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        title="Navigation"
        side="left"
        width="w-[248px]"
        hideHeader
        className="bg-forest-900"
      >
        <div className="flex h-full flex-col bg-forest-900">
          {showsTopbarTools(role, pathname) && (
            <div className="px-3 pt-3 md:hidden">
              <GlobalSearch />
            </div>
          )}
          <div className="min-h-0 flex-1">
            <SidebarContent onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      </Drawer>
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main id="main" className="min-w-0 flex-1" tabIndex={-1}>
          {/* No AnimatePresence/exit here: an exiting wrapper keeps rendering <Outlet />, which
              already shows the NEW route, and with lazy pages + router transitions the new page
              could stay stuck at opacity 0 until a reload. Pages fade in via PageContainer. */}
          <ErrorBoundary key={pathname}>
            {role ? <Outlet /> : <PageSkeleton />}
          </ErrorBoundary>
        </main>
      </div>
      <Toaster />
    </div>
  );
}
