import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/core/utils/cn';
import { dialogVariants, overlayVariants, transition } from '../motion/tokens';
import { IconButton } from './IconButton';
import { useFocusTrap } from './internal/useFocusTrap';
import { useLockBodyScroll } from './internal/useLockBodyScroll';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  /** Prevent closing on backdrop click (e.g. while a request runs). */
  dismissible?: boolean;
  role?: 'dialog' | 'alertdialog';
}

const SIZES = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl' } as const;

export function Dialog({ open, onClose, title, description, children, footer, size = 'md', dismissible = true, role = 'dialog' }: DialogProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = `dlg${useId().replace(/:/g, '')}`;
  const descId = description ? `${titleId}-desc` : undefined;
  useFocusTrap(ref, open, dismissible ? onClose : undefined);
  useLockBodyScroll(open);

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center">
          <motion.div
            className="absolute inset-0 bg-forest-950/40"
            variants={overlayVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            onClick={dismissible ? onClose : undefined}
            aria-hidden
          />
          <motion.div
            ref={ref}
            role={role}
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={descId}
            tabIndex={-1}
            variants={dialogVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            className={cn('relative flex max-h-[calc(100dvh-2rem)] w-full flex-col overflow-hidden rounded-card border border-line bg-surface shadow-2 focus:outline-none', SIZES[size])}
          >
            <div className="flex shrink-0 items-start justify-between gap-4 px-6 pb-2 pt-5">
              <div className="min-w-0 flex-1">
                <h2 id={titleId} className="text-lg font-semibold leading-snug text-ink break-words">
                  {title}
                </h2>
                {description && (
                  <p id={descId} className="mt-1 break-words text-base leading-snug text-muted">
                    {description}
                  </p>
                )}
              </div>
              {dismissible && <IconButton label="Close" icon={<X className="h-4 w-4" />} size="sm" onClick={onClose} />}
            </div>
            {children && <div className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-6 py-3">{children}</div>}
            {footer && <div className="flex shrink-0 justify-end gap-2 border-t border-line px-6 py-4">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children?: ReactNode;
  footer?: ReactNode;
  side?: 'left' | 'right';
  width?: string;
  /** Hide the visible header (the title stays as the accessible name). */
  hideHeader?: boolean;
  className?: string;
}

export function Drawer({ open, onClose, title, children, footer, side = 'right', width = 'w-[420px]', hideHeader, className }: DrawerProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = `drw${useId().replace(/:/g, '')}`;
  useFocusTrap(ref, open, onClose);
  useLockBodyScroll(open);
  const offset = side === 'right' ? '100%' : '-100%';

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div
            className="absolute inset-0 bg-forest-950/40"
            variants={overlayVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            initial={{ x: offset }}
            animate={{ x: 0, transition: transition('slow') }}
            exit={{ x: offset, transition: transition('base') }}
            className={cn(
              'absolute top-0 flex h-[100dvh] max-w-[90vw] flex-col bg-surface shadow-2 focus:outline-none',
              side === 'right' ? 'right-0 border-l border-line' : 'left-0',
              width,
              className,
            )}
          >
            <div className={cn('flex shrink-0 items-center justify-between border-b border-line px-5 py-4', hideHeader && 'sr-only')}>
              <h2 id={titleId} className="text-lg font-semibold text-ink">
                {title}
              </h2>
              {!hideHeader && <IconButton label="Close" icon={<X className="h-4 w-4" />} size="sm" onClick={onClose} />}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">{children}</div>
            {footer && <div className="flex shrink-0 justify-end gap-2 border-t border-line px-5 py-4">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
