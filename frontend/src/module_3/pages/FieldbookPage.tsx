import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { NotFound } from '@/shared/components/NotFound';
import { PageSkeleton } from '@/shared/components/PageSkeleton';
import FieldbookEntryPage from './FieldbookEntryPage';

const FieldbookEditorPage = lazy(() => import('./FieldbookEditorPage'));
const FieldbookViewPage = lazy(() => import('./FieldbookViewPage'));

/**
 * Module 3's own routes, mounted by the app router at `/fieldbook/*`.
 *
 * | Path                              | Page                                   |
 * | --------------------------------- | -------------------------------------- |
 * | `/fieldbook`                      | choose farmer and field (deep linkable) |
 * | `/fieldbook/books/:bookId`        | editor (a draft)                       |
 * | `/fieldbook/books/:bookId/view`   | read-only summary                      |
 */
export default function FieldbookPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route index element={<FieldbookEntryPage />} />
        <Route path="books/:bookId" element={<FieldbookEditorPage />} />
        <Route path="books/:bookId/view" element={<FieldbookViewPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
