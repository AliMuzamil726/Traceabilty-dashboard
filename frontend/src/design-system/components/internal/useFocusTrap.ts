import { useEffect, type RefObject } from 'react';

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Keep Tab focus inside `ref` while active, close on Escape, restore focus on exit. */
export function useFocusTrap(
  ref: RefObject<HTMLElement | null>,
  active: boolean,
  onEscape?: () => void,
): void {
  useEffect(() => {
    if (!active) return;
    const previous = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const focusables = () =>
      node ? Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => !el.hasAttribute('data-focus-skip')) : [];
    const first = focusables()[0];
    (first ?? node)?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onEscape?.();
        return;
      }
      if (event.key !== 'Tab' || !node) return;
      const items = focusables();
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const firstItem = items[0]!;
      const lastItem = items[items.length - 1]!;
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      previous?.focus?.();
    };
  }, [active, ref, onEscape]);
}
