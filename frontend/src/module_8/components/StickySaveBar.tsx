import { AnimatePresence, motion } from 'framer-motion';
import { Button } from '@/design-system/components/Button';
import { transition } from '@/design-system/motion';

export interface StickySaveBarProps {
  dirty: boolean;
  saving?: boolean;
  onSave: () => void;
  onDiscard: () => void;
  /** Shown on the left, e.g. "3 changes" or a warning about what a save affects. */
  message?: string;
  saveLabel?: string;
}

/**
 * The bar that appears at the bottom of a settings page once something has changed.
 *
 * It only exists while the form is dirty, so a page that has not been touched has no
 * enabled Save button to click by accident, and a page that has been touched can never
 * be left without the change being visible.
 */
export function StickySaveBar({
  dirty,
  saving = false,
  onSave,
  onDiscard,
  message,
  saveLabel = 'Save changes',
}: StickySaveBarProps) {
  return (
    <AnimatePresence>
      {dirty && (
        <motion.div
          initial={{ y: 16, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 16, opacity: 0 }}
          transition={transition('base')}
          role="region"
          aria-label="Unsaved changes"
          className="sticky bottom-0 z-20 -mx-4 mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface/95 px-4 py-3 shadow-2 backdrop-blur sm:-mx-6 sm:px-6"
        >
          <p className="text-sm text-muted">{message ?? 'You have unsaved changes.'}</p>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={onDiscard} disabled={saving}>
              Discard
            </Button>
            <Button onClick={onSave} loading={saving}>
              {saveLabel}
            </Button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export interface ChangedMarkerProps {
  changed: boolean;
}

/** A quiet "Changed" tag next to a field whose value differs from the saved one. */
export function ChangedMarker({ changed }: ChangedMarkerProps) {
  if (!changed) return null;
  return (
    <span className="rounded-pill bg-wheat-100 px-2 py-0.5 text-xs font-medium text-forest-950">
      Changed
    </span>
  );
}
