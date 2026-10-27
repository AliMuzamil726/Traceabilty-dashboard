import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, Copy, Trash2 } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/core/utils/cn';
import { Button } from '@/design-system/components';
import { transition } from '@/design-system/motion';

export interface EntryAccordionProps {
  title: string;
  summary: string;
  open: boolean;
  onToggle: () => void;
  onDuplicate?: () => void;
  onDelete?: () => void;
  unsaved?: boolean;
  children: ReactNode;
  footer?: ReactNode;
}

/** One entry of a repeatable step: a summary line that opens into its form. */
export function EntryAccordion({ title, summary, open, onToggle, onDuplicate, onDelete, unsaved, children, footer }: EntryAccordionProps) {
  return (
    <div className={cn('rounded-lg border bg-surface', open ? 'border-forest-500' : 'border-line')}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-ink">
            {title}
            {unsaved && <span className="ml-2 text-xs font-medium text-wheat-600">Not saved</span>}
          </span>
          <span className="block truncate text-sm text-muted">{summary}</span>
        </span>
        <ChevronDown className={cn('h-4 w-4 shrink-0 text-muted transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={transition('base')}
            className="overflow-hidden"
          >
            <div className="border-t border-line px-4 py-4">{children}</div>
            <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-3">
              {onDuplicate && (
                <Button type="button" variant="ghost" size="sm" leftIcon={<Copy className="h-4 w-4" />} onClick={onDuplicate}>
                  Duplicate
                </Button>
              )}
              {onDelete && (
                <Button type="button" variant="ghost" size="sm" leftIcon={<Trash2 className="h-4 w-4" />} onClick={onDelete}>
                  Delete
                </Button>
              )}
              <span className="flex-1" />
              {footer}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
