import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { PageContainer } from '@/app/layout/PageContainer';
import { PageHeader } from '@/design-system/components/PageHeader';
import { PageSkeleton } from '@/shared/components/PageSkeleton';
import { AdminOnlyGate } from '../components/AdminOnlyGate';
import { SettingsNav } from '../components/SettingsNav';

const OfficersPage = lazy(() => import('./OfficersPage'));
const PermissionsPage = lazy(() => import('./PermissionsPage'));
const OfficesPage = lazy(() => import('./OfficesPage'));
const CropsSeasonPage = lazy(() => import('./CropsSeasonPage'));
const SitesPage = lazy(() => import('./SitesPage'));
const ListsPage = lazy(() => import('./ListsPage'));
const LocationsPage = lazy(() => import('./LocationsPage'));
const DeliveryHeapPage = lazy(() => import('./DeliveryHeapPage'));
const AlertsPage = lazy(() => import('./AlertsPage'));
const ValidationPage = lazy(() => import('./ValidationPage'));
const MapPage = lazy(() => import('./MapPage'));
const QrLabelsPage = lazy(() => import('./QrLabelsPage'));
const AuditPage = lazy(() => import('./AuditPage'));
const BackupPage = lazy(() => import('./BackupPage'));
const SystemPage = lazy(() => import('./SystemPage'));
const PreferencesPage = lazy(() => import('./PreferencesPage'));

/** Everything except preferences needs an administrator. */
function AdminSection() {
  return (
    <AdminOnlyGate>
      <Outlet />
    </AdminOnlyGate>
  );
}

export default function SettingsLayout() {
  return (
    <PageContainer>
      <PageHeader
        title="Settings"
        subtitle="People, lists, locations and the numbers the rest of the product works from."
      />
      <div className="mt-6 grid gap-6 lg:grid-cols-[232px_minmax(0,1fr)]">
        <div className="lg:sticky lg:top-24 lg:self-start">
          <SettingsNav />
        </div>
        <div className="min-w-0">
          <Suspense fallback={<PageSkeleton />}>
            <Routes>
              <Route index element={<Navigate to="/settings/officers" replace />} />
              <Route path="preferences" element={<PreferencesPage />} />
              <Route element={<AdminSection />}>
                <Route path="officers" element={<OfficersPage />} />
                <Route path="permissions" element={<PermissionsPage />} />
                <Route path="offices" element={<OfficesPage />} />
                <Route path="crops" element={<CropsSeasonPage />} />
                <Route path="sites" element={<SitesPage />} />
                <Route path="lists" element={<ListsPage />} />
                <Route path="locations" element={<LocationsPage />} />
                <Route path="deliveries" element={<DeliveryHeapPage />} />
                <Route path="alerts" element={<AlertsPage />} />
                <Route path="validation" element={<ValidationPage />} />
                <Route path="map" element={<MapPage />} />
                <Route path="qr" element={<QrLabelsPage />} />
                <Route path="audit" element={<AuditPage />} />
                <Route path="backup" element={<BackupPage />} />
                <Route path="system" element={<SystemPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/settings/officers" replace />} />
            </Routes>
          </Suspense>
        </div>
      </div>
    </PageContainer>
  );
}
