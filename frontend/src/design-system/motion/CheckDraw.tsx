import { motion } from 'framer-motion';
import { DURATION, EASE } from './tokens';

interface CheckDrawProps {
  size?: number;
  className?: string;
  label?: string;
}

/** Short check-draw used for success states. Respects MotionConfig reducedMotion. */
export function CheckDraw({ size = 20, className, label = 'Done' }: CheckDrawProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} role="img" aria-label={label}>
      <motion.circle
        cx="12"
        cy="12"
        r="10"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        initial={{ pathLength: 0, opacity: 0.4 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: DURATION.slow, ease: EASE }}
      />
      <motion.path
        d="M7.5 12.5l3 3 6-6.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: DURATION.base, ease: EASE, delay: DURATION.fast }}
      />
    </svg>
  );
}
