import { useEffect } from 'react';
import { useBlocker } from 'react-router-dom';

/**
 * Keeps unsaved answers from being lost: the browser asks before closing the tab, and
 * in-app navigation is held so the page can ask with its own dialog.
 */
export function useUnsavedGuard(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return undefined;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  return useBlocker(({ currentLocation, nextLocation }) => dirty && currentLocation.pathname !== nextLocation.pathname);
}
