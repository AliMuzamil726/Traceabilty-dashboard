import { AnimatePresence, motion } from 'framer-motion';
import { cloneElement, isValidElement, useId, useRef, useState, type ReactElement, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/core/utils/cn';
import { transition } from '../motion/tokens';

export interface TooltipProps {
  content: ReactNode;
  children: ReactElement;
  side?: 'top' | 'right' | 'bottom';
  disabled?: boolean;
  delay?: number;
}

const SIDE = {
  top: '-translate-x-1/2 -translate-y-full',
  bottom: '-translate-x-1/2',
  right: '-translate-y-1/2',
} as const;

/** Where the tooltip sits, from the trigger's box on screen (8px gap). */
function place(rect: DOMRect, side: keyof typeof SIDE): { left: number; top: number } {
  if (side === 'right') return { left: rect.right + 8, top: rect.top + rect.height / 2 };
  if (side === 'bottom') return { left: rect.left + rect.width / 2, top: rect.bottom + 8 };
  return { left: rect.left + rect.width / 2, top: rect.top - 8 };
}

/** Shows on hover and keyboard focus; linked to its trigger with aria-describedby. */
export function Tooltip({ content, children, side = 'top', disabled = false, delay = 250 }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ left: 0, top: 0 });
  const wrapper = useRef<HTMLSpanElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const id = `tt${useId().replace(/:/g, '')}`;

  if (disabled || !isValidElement(children)) return children;

  const show = () => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      // Rendered on the page body so a scrolling or clipped parent (the sidebar) never cuts it off.
      if (wrapper.current) setPos(place(wrapper.current.getBoundingClientRect(), side));
      setOpen(true);
    }, delay);
  };
  const hide = () => {
    window.clearTimeout(timer.current);
    setOpen(false);
  };

  const trigger = cloneElement(children as ReactElement<Record<string, unknown>>, {
    'aria-describedby': open ? id : undefined,
  });

  return (
    // The wrapper only listens to events bubbling from the focusable trigger it wraps.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <span
      ref={wrapper}
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      onKeyDown={(e) => e.key === 'Escape' && hide()}
    >
      {trigger}
      {createPortal(
      <AnimatePresence>
        {open && (
          <span key="tt" className={cn('pointer-events-none fixed z-[80]', SIDE[side])} style={pos}>
            <motion.span
              id={id}
              role="tooltip"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1, transition: transition('fast') }}
              exit={{ opacity: 0, transition: transition('fast') }}
              className="block whitespace-nowrap rounded-sm bg-forest-950 px-2 py-1 text-xs font-medium text-white shadow-2"
            >
              {content}
            </motion.span>
          </span>
        )}
      </AnimatePresence>,
      document.body,
      )}
    </span>
  );
}
