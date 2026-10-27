import { lazy, Suspense, type ComponentType } from 'react';
import { createBrowserRouter, type RouteObject } from 'react-router-dom';
import { ErrorBoundary } from '@/shared/components/ErrorBoundary';
import { NotFound } from '@/shared/components/NotFound';
import { PageSkeleton } from '@/shared/components/PageSkeleton';
import { AppShell } from './layout/AppShell';
import { PageContainer } from './layout/PageContainer';
import { ROUTABLE_MODULES, type ModuleLoader } from './moduleRegistry';

/** These modules frame their own pages (some are full-bleed); the rest get the standard frame. */
const SELF_FRAMED = new Set(['/', '/register', '/settings']);

function lazyPage(loader: ModuleLoader, framed = false): ComponentType {
  const Page = lazy(loader);
  return function LazyModulePage() {
    return (
      <ErrorBoundary>
        <Suspense fallback={<PageSkeleton />}>
          {framed ? (
            <PageContainer>
              <Page />
            </PageContainer>
          ) : (
            <Page />
          )}
        </Suspense>
      </ErrorBoundary>
    );
  };
}

export function buildRoutes(): RouteObject[] {
  const children: RouteObject[] = ROUTABLE_MODULES.map((m) => {
    const Page = lazyPage(m.loader as ModuleLoader, !SELF_FRAMED.has(m.path));
    return m.path === '/' ? { index: true, element: <Page /> } : { path: `${m.path.slice(1)}/*`, element: <Page /> };
  });
  children.push({ path: '*', element: <NotFound /> });
  // The page a scanned label opens: public, mobile-first, outside the app shell.
  const PublicTrace = lazyPage(() => import('@/module_7').then((m) => m.loadPublicTracePage()));
  const Login = lazyPage(() => import('./pages/LoginPage'));
  const Profile = lazyPage(() => import('./pages/ProfilePage'));
  children.splice(children.length - 1, 0, { path: 'profile', element: <Profile /> });
  return [
    { path: '/trace/:token', element: <PublicTrace /> },
    { path: '/login', element: <Login /> },
    { path: '/', element: <AppShell />, children },
  ];
}

export const router = createBrowserRouter(buildRoutes());
