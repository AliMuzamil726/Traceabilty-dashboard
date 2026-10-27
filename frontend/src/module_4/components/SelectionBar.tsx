import { AnimatePresence, motion } from 'framer-motion';
import { Download, Truck, X } from 'lucide-react';
import { Button, Tooltip } from '@/design-system/components';
import { transition } from '@/design-system/motion';

export interface SelectionBarProps {
  count: number;
  blockers: string[];
  exporting: boolean;
  onRequest: () => void;
  onExport: () => void;
  onClear: () => void;
}

/** Floats over the page while rows are selected. */
export function SelectionBar({ count, blockers, exporting, onRequest, onExport, onClear }: SelectionBarProps) {
  const blocked = blockers.length > 0;
  return (
    <AnimatePresence>
      {count > 0 && (
        <motion.div
          role="region"
          aria-label="Selected fields"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 16 }}
          transition={transition('base')}
          className="fixed bottom-4 left-1/2 z-30 flex -translate-x-1/2 flex-wrap items-center gap-3 rounded-card border border-line bg-surface px-4 py-3 shadow-2"
        >
          <span className="text-sm font-medium text-ink">
            {count} {count === 1 ? 'field' : 'fields'} selected
          </span>
          <Tooltip
            disabled={!blocked}
            content={
              <ul className="flex flex-col gap-1 text-left">
                {blockers.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            }
          >
            {/* aria-disabled, not disabled: the button stays focusable so the reasons can be read. */}
            <Button
              size="sm"
              leftIcon={<Truck className="h-4 w-4" />}
              aria-disabled={blocked || undefined}
              aria-describedby={blocked ? 'request-blockers' : undefined}
              className={blocked ? 'cursor-not-allowed opacity-50' : undefined}
              onClick={() => !blocked && onRequest()}
            >
              Request pickup
            </Button>
          </Tooltip>
          {blocked && (
            <span id="request-blockers" className="sr-only">
              {blockers.join('. ')}
            </span>
          )}
          <Button size="sm" variant="secondary" leftIcon={<Download className="h-4 w-4" />} loading={exporting} onClick={onExport}>
            Export CSV
          </Button>
          <Button size="sm" variant="ghost" leftIcon={<X className="h-4 w-4" />} onClick={onClear}>
            Clear
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
