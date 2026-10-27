import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { NotFound } from '@/shared/components/NotFound';
import { PageSkeleton } from '@/shared/components/PageSkeleton';
import FarmerListPage from './FarmerListPage';

// The form and the map carry the heavier dependencies (react-hook-form, Leaflet,
// Geoman, turf), so they load when an officer actually opens them.
const FarmerFormPage = lazy(() => import('./FarmerFormPage'));
const FarmerProfilePage = lazy(() => import('./FarmerProfilePage'));
const FieldMapPage = lazy(() => import('./FieldMapPage'));
const AddFieldLookupPage = lazy(() => import('./AddFieldLookupPage'));

/**
 * Module 2's own routes, mounted by the app router at `/register/*`.
 *
 * | Path                                               | Page                            |
 * | -------------------------------------------------- | ------------------------------- |
 * | `/register`                                        | farmer list                     |
 * | `/register/new`                                    | register form                   |
 * | `/register/add-field`                              | lookup farmer & add field       |
 * | `/register/farmers/:farmerId`                      | farmer profile                  |
 * | `/register/farmers/:farmerId/edit`                 | edit form                       |
 * | `/register/farmers/:farmerId/fields/new`           | map a new field                 |
 * | `/register/farmers/:farmerId/fields/:fieldId/edit` | reshape a field                 |
 */
export default function RegisterFarmerPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route index element={<FarmerListPage />} />
        <Route path="new" element={<FarmerFormPage />} />
        <Route path="add-field" element={<AddFieldLookupPage />} />
        <Route path="farmers/:farmerId" element={<FarmerProfilePage />} />
        <Route path="farmers/:farmerId/edit" element={<FarmerFormPage />} />
        <Route path="farmers/:farmerId/fields/new" element={<FieldMapPage />} />
        <Route path="farmers/:farmerId/fields/:fieldId/edit" element={<FieldMapPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
