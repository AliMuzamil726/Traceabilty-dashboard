import { useEffect } from 'react';

/**
 * Stop the page behind a modal from scrolling while it is open.
 *
 * Without this, a wheel or two-finger gesture over the panel can still scroll the page
 * underneath (the panel itself does not overflow), and on small screens that is what
 * makes a fixed panel appear to jump or vanish as the browser hides its toolbar.
 */
export function useLockBodyScroll(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [active]);
}
