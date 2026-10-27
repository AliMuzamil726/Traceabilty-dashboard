import { AnimatePresence, motion } from 'framer-motion';
import { AlertCircle, Info, X } from 'lucide-react';
import { cn } from '@/core/utils/cn';
import { CheckDraw } from '../motion/CheckDraw';
import { transition } from '../motion/tokens';

import { useToastStore, type ToastTone } from './toastStore';

const ACCENT: Record<ToastTone, string> = {
  success: 'text-forest-700',
  info: 'text-forest-700',
  warning: 'text-wheat-600',
  error: 'text-danger',
};

function ToastIcon({ tone }: { tone: ToastTone }) {
  if (tone === 'success') return <CheckDraw size={20} className={ACCENT.success} label="Success" />;
  if (tone === 'error') return <AlertCircle className={cn('h-5 w-5', ACCENT.error)} aria-hidden />;
  return <Info className={cn('h-5 w-5', ACCENT[tone])} aria-hidden />;
}

/** Global toast area (mounted once in the app shell). */
export function Toaster() {
  const { toasts, dismiss } = useToastStore();
  return (
    <div aria-live="polite" aria-relevant="additions" className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2">
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            role={t.tone === 'error' ? 'alert' : 'status'}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0, transition: transition('base') }}
            exit={{ opacity: 0, transition: transition('fast') }}
            className="pointer-events-auto flex items-start gap-3 rounded-card border border-line bg-surface p-4 shadow-2"
          >
            <ToastIcon tone={t.tone} />
            <div className="min-w-0 flex-1">
              <p className="font-medium text-ink">{t.title}</p>
              {t.description && <p className="mt-0.5 text-sm text-muted">{t.description}</p>}
            </div>
            <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss notification" className="rounded-sm text-muted hover:text-ink">
              <X className="h-4 w-4" aria-hidden />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
